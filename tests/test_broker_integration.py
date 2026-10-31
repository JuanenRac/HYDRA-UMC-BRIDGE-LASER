# =============================================================================
# HYDRA-UMC-BRIDGE-LASER - Integration with a real MQTT broker
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
"""This bridge's transport against a real HYDRA-UMC-MQTT-BROKER on a free local port (see broker_harness.py).

The tests skip themselves when node, paho-mqtt or the installed broker checkout are not there, so the ordinary run does not need a broker.
"""

import unittest

import broker_harness as harness
from hydra_umc_sdk.bridge_contract import CellState

from hydra_umc_bridge_laser import GpioSafetyLines, LaserMqttBridge

from hydra_umc_bridge_laser.mqtt_transport import TOPIC_PREFIX, MessageDispatcher


class Line:
    def __init__(self, value: bool = True) -> None:
        self.value = value

    def read(self) -> bool:
        return self.value


class LaserOverBroker(harness.BridgeOverBrokerCases):
    PREFIX = TOPIC_PREFIX
    COMMAND_VERB = "job"

    def make_bridge(self) -> object:
        return LaserMqttBridge(GpioSafetyLines(Line(True), Line(True), Line(True)), lambda: "IDLE", lambda: CellState.READY)

    def make_dispatcher(self, bridge: object) -> object:
        return MessageDispatcher(bridge)

    def command_payload(self) -> bytes:
        return b"{this is not json"

    def answer_is_right(self, body: dict) -> bool:
        return body.get("allowed") is False and "malformed" in str(body.get("reason", ""))

    def test_the_answer_of_the_bridge_travels_at_qos_1(self) -> None:
        # the laser bridge's answers are EventPublish messages: QoS 1, and the broker must hand them on at QoS 1
        self.start_bridge()
        asker = self.collector("qosasker")
        asker.subscribe(f"{self.PREFIX}availability")
        self.wait_online(asker)
        asker.subscribe(self.result_topic, 2)
        self.assertIsNotNone(self.ask(asker, 1))
        self.assertEqual(self.last_answer_qos, 1)


if __name__ == "__main__":
    unittest.main()
