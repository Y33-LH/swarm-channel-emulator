---
name: swarm-uart-recovery
description: Diagnose truncated serial JSON, stale responses, or unavailable UART on this Zynq swarm project without masking missing receive data or silently changing the experiment.
---

Use the project root two directories above this file. Read `tools/serial_json.py`, `tools/network_wire.py`, and the failed run's raw UART log before editing transport code.

1. Distinguish an enumerated COM port from an openable device. A Windows device-not-functioning error requires cable/device recovery; increasing the parser timeout cannot repair it. Ask for one USB TO UART replug if needed, preserving external power and JTAG.
2. Ensure a single serial owner. A UI process may remain alive while idle; do not kill unrelated Python processes. Stop only the identified project service if necessary.
3. Preserve partial bytes between reads until a complete newline arrives. Validate JSON framing and request identity. Do not discard malformed result data and then report success from a later unrelated response.
4. Keep the established 230400 baud unless changing both firmware and host with measured validation. A bigger network snapshot is not evidence that a higher baud is electrically reliable.
5. For compact telemetry, validate encoded length, field count, integer bounds, and full/fast equality using `tests/test_network_wire.py` and the mixed-node board test. Compression must not omit failed frames, packets, or model rounds.
6. Reconnect, verify the manifest version, and reset test-owned parameters explicitly. A prior test may leave noise, gain, load, or error injection active. Never silently replace failed receive bytes with the transmit buffer.
7. Re-run the failed operation and its recovery test. Keep both failed and successful evidence. Report whether the fault was transport, hardware execution, receive decoding, or application validation.
