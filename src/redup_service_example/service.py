import sys

import asyncio
import logging
import signal

import grpc
from redup_proto_textprocessor.redup.textprocessor.v1.textprocessor_pb2 import (
    DESCRIPTOR,
    ProcessTextResponse,
)
from redup_proto_textprocessor.redup.textprocessor.v1.textprocessor_pb2_grpc import (
    TextProcessorServicer,
    add_TextProcessorServicer_to_server,
)
from grpc_reflection.v1alpha import reflection
from redup_servicekit.config import ConfigSingleton
from redup_servicekit.health import HEALTH_DESCRIPTOR, _configure_health_server
from redup_servicekit.logging import init_console_log
from redup_servicekit.monitoring import MonitorServer
from redup_servicekit.grpc.decorators import aio_grpc_method_wrapper, grpc_init_wrapper

from .prototype import Example


class Server(TextProcessorServicer):
    @grpc_init_wrapper
    def __init__(self, worker: Example):
        self._worker = worker

    @aio_grpc_method_wrapper
    async def ProcessText(self, request, context, metrics, **kwargs):
        logging.info("{}: request ProcessText".format(request.request_id))
        metrics["id"] = request.request_id

        result, request_metrics = await self._worker.process_text(
            request_id=request.request_id,
            text=request.text
        )
        metrics.update(request_metrics)

        response = ProcessTextResponse(**result)

        logging.info("{}: response ProcessText".format(request.request_id))
        return response


async def serve(path_to_cfg=None):
    ConfigSingleton.load(path_to_cfg)
    ConfigSingleton.inject_os_envs()

    config_obj = ConfigSingleton.get()

    init_console_log(config_obj["service"]["console_log_level"])

    logging.info("Initializing Example service")
    worker = Example(config_obj["Example"])

    MonitorServer().run(
        config_obj.get("MonitorServer", {}),
        max_workers=int(config_obj["service"]["max_workers"]),
        hpa_max_workers=int(config_obj["service"]["hpa_max_workers"]),
    )

    maximum_concurrent_rpcs = int(config_obj["service"]["grpc_queue_size"])
    if maximum_concurrent_rpcs <= 0:
        maximum_concurrent_rpcs = None
    server = grpc.aio.server(
        options=config_obj["service"]["grpc_msg_opts"]["options"],
        maximum_concurrent_rpcs=maximum_concurrent_rpcs,
    )

    add_TextProcessorServicer_to_server(Server(worker), server)
    SERVICE_NAMES = (
        DESCRIPTOR.services_by_name["TextProcessor"].full_name,
        HEALTH_DESCRIPTOR.services_by_name["Health"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)
    _configure_health_server(
        server, DESCRIPTOR.services_by_name["TextProcessor"].full_name
    )

    server.add_insecure_port(config_obj["service"]["port"])

    logging.info("Server running on port {}".format(config_obj["service"]["port"]))
    await server.start()

    async def server_graceful_shutdown():
        logging.info("Starting graceful shutdown...")
        await server.stop(5)

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(
        signal.SIGINT, lambda: asyncio.create_task(server_graceful_shutdown())
    )
    loop.add_signal_handler(
        signal.SIGTERM, lambda: asyncio.create_task(server_graceful_shutdown())
    )

    await server.wait_for_termination()


def start():
    asyncio.run(serve(sys.argv[1]))


if __name__ == "__main__":
    start()