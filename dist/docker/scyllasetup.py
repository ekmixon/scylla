import subprocess
import logging
import yaml
import os


class ScyllaSetup:
    def __init__(self, arguments, extra_arguments):
        self._developerMode = arguments.developerMode
        self._seeds = arguments.seeds
        self._cpuset = arguments.cpuset
        self._listenAddress = arguments.listenAddress
        self._rpcAddress = arguments.rpcAddress
        self._alternatorAddress = arguments.alternatorAddress
        self._broadcastAddress = arguments.broadcastAddress
        self._broadcastRpcAddress = arguments.broadcastRpcAddress
        self._apiAddress = arguments.apiAddress
        self._alternatorPort = arguments.alternatorPort
        self._alternatorHttpsPort = arguments.alternatorHttpsPort
        self._alternatorWriteIsolation = arguments.alternatorWriteIsolation
        self._smp = arguments.smp
        self._memory = arguments.memory
        self._reserveMemory = arguments.reserveMemory
        self._overprovisioned = arguments.overprovisioned
        self._housekeeping = not arguments.disable_housekeeping
        self._experimental = arguments.experimental
        self._authenticator = arguments.authenticator
        self._authorizer = arguments.authorizer
        self._clusterName = arguments.clusterName
        self._endpointSnitch = arguments.endpointSnitch
        self._replaceAddressFirstBoot = arguments.replaceAddressFirstBoot
        self._io_setup = arguments.io_setup
        self._extra_args = extra_arguments

    def _run(self, *args, **kwargs):
        logging.info(f'running: {args}')
        subprocess.check_call(*args, **kwargs)

    def developerMode(self):
        self._run(['/opt/scylladb/scripts/scylla_dev_mode_setup', '--developer-mode', self._developerMode])

    def cpuSet(self):
        if self._cpuset is None:
            return
        self._run(['/opt/scylladb/scripts/scylla_cpuset_setup', '--cpuset', self._cpuset])

    def io(self):
        conf_dir = "/etc/scylla"
        cfg = yaml.safe_load(open(os.path.join(conf_dir, "scylla.yaml")))
        if 'workdir' not in cfg or not cfg['workdir']:
            cfg['workdir'] = '/var/lib/scylla'
        if 'data_file_directories' not in cfg or \
                    not cfg['data_file_directories'] or \
                    not len(cfg['data_file_directories']) or \
                    not " ".join(cfg['data_file_directories']).strip():
            cfg['data_file_directories'] = [os.path.join(cfg['workdir'], 'data')]

        data_dirs = cfg["data_file_directories"]
        if len(data_dirs) > 1:
            logging.warn("%d data directories found. scylla_io_setup currently lacks support for it, and only %s will be evaluated",
                         len(data_dirs), data_dirs[0])
        data_dir = data_dirs[0]
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        if self._io_setup == "1":
            self._run(['/opt/scylladb/scripts/scylla_io_setup'])

    def cqlshrc(self):
        home = os.environ['HOME']
        hostname = subprocess.check_output(['hostname', '-i']).decode('ascii').strip()
        with open(f"{home}/.cqlshrc", "w") as cqlshrc:
            cqlshrc.write("[connection]\nhostname = %s\n" % hostname)

    def set_housekeeping(self):
        with open("/etc/scylla.d/housekeeping.cfg", "w") as f:
            f.write("[housekeeping]\ncheck-version: ")
            if self._housekeeping:
                f.write("True\n")
            else:
                f.write("False\n")

    def arguments(self):
        args = []
        if self._memory is not None:
            args += [f"--memory {self._memory}"]

        if self._reserveMemory is not None:
            args += [f"--reserve-memory {self._reserveMemory}"]

        if self._smp is not None:
            args += [f"--smp {self._smp}"]

        if self._overprovisioned == "1" or (self._overprovisioned is None and self._cpuset is None):
            args += ["--overprovisioned"]

        if self._listenAddress is None:
            self._listenAddress = subprocess.check_output(['hostname', '-i']).decode('ascii').strip()

        if self._rpcAddress is None:
            self._rpcAddress = self._listenAddress

        if self._alternatorAddress is None:
            self._alternatorAddress = self._listenAddress

        if self._seeds is None:
            if self._broadcastAddress is not None:
                self._seeds = self._broadcastAddress
            else:
                self._seeds = self._listenAddress

        args += [
            f"--listen-address {self._listenAddress}",
            f"--rpc-address {self._rpcAddress}",
            f"--seed-provider-parameters seeds={self._seeds}",
        ]


        if self._broadcastAddress is not None:
            args += [f"--broadcast-address {self._broadcastAddress}"]
        if self._broadcastRpcAddress is not None:
            args += [f"--broadcast-rpc-address {self._broadcastRpcAddress}"]

        if self._apiAddress is not None:
            args += [f"--api-address {self._apiAddress}"]

        if self._alternatorPort is not None:
            args += [f"--alternator-address {self._alternatorAddress}"]
            args += [f"--alternator-port {self._alternatorPort}"]

        if self._alternatorHttpsPort is not None:
            args += [f"--alternator-address {self._alternatorAddress}"]
            args += [f"--alternator-https-port {self._alternatorHttpsPort}"]

        if self._alternatorWriteIsolation is not None:
            args += [f"--alternator-write-isolation {self._alternatorWriteIsolation}"]

        if self._authenticator is not None:
            args += [f"--authenticator {self._authenticator}"]

        if self._authorizer is not None:
            args += [f"--authorizer {self._authorizer}"]

        if self._experimental == "1":
            args += ["--experimental=on"]

        if self._clusterName is not None:
            args += [f"--cluster-name {self._clusterName}"]

        if self._endpointSnitch is not None:
            args += [f"--endpoint-snitch {self._endpointSnitch}"]

        if self._replaceAddressFirstBoot is not None:
            args += [f"--replace-address-first-boot {self._replaceAddressFirstBoot}"]

        args += ["--blocked-reactor-notify-ms 999999999"]

        with open("/etc/scylla.d/docker.conf", "w") as cqlshrc:
            cqlshrc.write("SCYLLA_DOCKER_ARGS=\"%s\"\n" % (" ".join(args) + " " + " ".join(self._extra_args)))
