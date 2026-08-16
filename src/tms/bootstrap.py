from __future__ import annotations

from dataclasses import dataclass

from .accounts.repository import AccountRepository
from .accounts.service import AccountService
from .config import AppPaths, Settings
from .datasets.repository import DatasetRepository
from .datasets.service import DatasetService
from .groups.repository import GroupRepository
from .groups.service import GroupService
from .import_export.service import ImportExportService
from .jobs.repository import JobRepository
from .members.repository import MemberRepository
from .migration.planner import MigrationPlanner
from .migration.precheck import TargetPrecheck
from .migration.recovery import RecoveryService
from .runtime.application_runtime import ApplicationRuntime
from .runtime.command_bus import CommandBus
from .runtime.command_handlers import CommandHandlers
from .runtime.db_writer import DBWriter
from .runtime.event_aggregator import EventAggregator
from .runtime.event_bus import EventBus
from .runtime.network_runtime import NetworkRuntime
from .runtime.performance_monitor import PerformanceMonitor
from .runtime.resource_governor import ResourceGovernor
from .runtime.state_store import StateStore
from .runtime.worker_pool import WorkerPool
from .storage.database import Database
from .telegram.auth_service import AuthService
from .telegram.client_manager import ClientManager
from .telegram.participant_scanner import ParticipantScanner
from .telegram.peer_cache import PeerCache
from .telegram.telethon_gateway import TelethonGateway
from .utilities.group_membership import GroupMembershipUtility
from .accounts.state_resolver import AccountStateResolver
from .workflows.coordinator import WorkflowCoordinator


@dataclass(slots=True)
class AppContext:
    paths: AppPaths
    settings: Settings
    database: Database
    runtime: ApplicationRuntime
    commands: CommandBus
    state: StateStore
    metrics: PerformanceMonitor
    accounts: AccountRepository
    account_service: AccountService
    groups: GroupRepository
    group_service: GroupService
    members: MemberRepository
    datasets: DatasetRepository
    dataset_service: DatasetService
    jobs: JobRepository
    peers: PeerCache
    clients: ClientManager
    auth: AuthService
    gateway: TelethonGateway
    scanner: ParticipantScanner
    precheck: TargetPrecheck
    planner: MigrationPlanner
    recovery: RecoveryService
    import_export: ImportExportService
    membership: GroupMembershipUtility
    account_states: AccountStateResolver
    workflows: WorkflowCoordinator | None = None
    command_handlers: CommandHandlers | None = None


def bootstrap() -> AppContext:
    paths = AppPaths.discover()
    settings = Settings.load(paths)
    database = Database(paths.data / "app.db")
    database.initialize()

    network = NetworkRuntime()
    events = EventBus()
    aggregator = EventAggregator()
    events.subscribe("*", aggregator.push)
    writer = DBWriter(database)
    governor = ResourceGovernor()
    runtime = ApplicationRuntime(
        network=network,
        governor=governor,
        events=events,
        ui_events=aggregator,
        workers=WorkerPool(2),
        db_writer=writer,
    )
    commands = CommandBus()
    state = StateStore()
    metrics = PerformanceMonitor()

    accounts = AccountRepository(database, writer)
    groups = GroupRepository(database, writer)
    members = MemberRepository(database, writer)
    datasets = DatasetRepository(database, writer)
    jobs = JobRepository(database, writer)
    peers = PeerCache(database, writer)
    account_service = AccountService(accounts, paths.sessions)
    dataset_service = DatasetService(datasets)

    clients = ClientManager(network, settings.api_id, settings.api_hash)

    def session_lookup(account_id: int) -> str:
        account = accounts.get(account_id)
        if account is None:
            raise KeyError(f"Unknown account id: {account_id}")
        return account.session_path

    auth = AuthService(clients, accounts, session_lookup)
    gateway = TelethonGateway(clients, accounts, peers)
    group_service = GroupService(gateway)
    scanner = ParticipantScanner(
        gateway,
        members,
        datasets,
        peers,
        jobs,
        events,
        governor,
    )
    precheck = TargetPrecheck(governor)
    planner = MigrationPlanner(database, jobs)
    recovery = RecoveryService(jobs)
    import_export = ImportExportService(datasets, members, jobs, events)
    membership = GroupMembershipUtility(gateway, governor)

    context = AppContext(
        paths=paths,
        settings=settings,
        database=database,
        runtime=runtime,
        commands=commands,
        state=state,
        metrics=metrics,
        accounts=accounts,
        account_service=account_service,
        groups=groups,
        group_service=group_service,
        members=members,
        datasets=datasets,
        dataset_service=dataset_service,
        jobs=jobs,
        peers=peers,
        clients=clients,
        auth=auth,
        gateway=gateway,
        scanner=scanner,
        precheck=precheck,
        planner=planner,
        recovery=recovery,
        import_export=import_export,
        membership=membership,
        account_states=AccountStateResolver(accounts, jobs),
    )
    context.workflows = WorkflowCoordinator(context)
    handlers = CommandHandlers(context)
    handlers.register_all()
    context.command_handlers = handlers
    runtime.add_network_shutdown_hook(handlers.prepare_shutdown)
    runtime.add_network_shutdown_hook(clients.close_all)
    return context
