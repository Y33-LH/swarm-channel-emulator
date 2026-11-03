---
name: swarm-physical-acceptance
description: Qualify this repository's single-board Zynq swarm channel simulator after RTL, ARM firmware, serial transport, or UI control changes. Use for actual hardware acceptance and release decisions, not for generating simulated passing results.
---

Work from the project root two directories above this file. Read `docs/delivery_contract.txt`, `release.json`, and `docs/product_build.json` first. Respect the declared board, clock, protocol, and image hashes; do not infer them from an old console screenshot.

1. Keep one UART owner. Do not run direct serial tests while the UI has an active task. Inspect `/api/state` before choosing either route. Preserve existing accepted releases.
2. For RTL changes, run the reference/receive/AXI simulations, then `hw/build_board.tcl`. `hw/finish_board.tcl` rejects negative setup or hold slack. If post-route optimization was used, inspect the final `board_physopt.dcp` and associated reports; the earlier implementation checkpoint may still contain a failing result. Do not suppress DRC warnings to obtain a pass.
3. Rebuild ARM against the matching HDF. `tools/check_clean_sdk.py` compares loadable ELF content, because debug paths can change the full ELF hash without changing the executable. Record both kinds of comparison accurately.
4. Program BIT, PS initialization and ELF from the same manifest. Require both a successful process and `PROGRAM_RUN_FINISHED`. A Tcl error printed by XSCT is not reliably represented by its default process exit status.
5. Run `tools/qualify_delivery.py` sequentially. Receipts bind image hashes, test hashes, and evidence hashes. On failure, preserve the failed directory, fix the cause, and resume with `--from-test`; do not edit a test while it is running.
6. Complete summaries and code edits before freezing `release.json` as `results/freeze_input_manifest.json`. Run the real assistant/UI hardware tests on that frozen source. Require three distinct 900-second runs, actual returned media bytes, stop/restart, and command execution confirmed by a received heartbeat.
7. Use `tools/finalize_delivery.py --prepare` before the freeze and `--accept` after all gates. Switch the stable launcher only after acceptance. A changed executable or receiver requires new evidence; old passing output never substitutes for a current test.

Keep final delivery, timely delivery, model time, wall time, BER, and missing-ACK retries separate. PL endpoints 9/13 are independent board-internal hardware endpoints, not external aircraft. Scene presets and maps are not validated terrain/weather propagation models. Automated engineering acceptance does not establish novice-user usability or completion of the competition submission.
