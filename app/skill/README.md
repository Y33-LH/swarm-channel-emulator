# Reproduce and extend a hardware-backed swarm experiment

This package records an AI-assisted engineering workflow. It is not a claim that
the language model, host UI or ARM implements the core modem in software.

## Inputs and ownership

- Board: wildfire xc7z020clg400-2; Vivado and SDK 2018.3.
- FPGA: independent hardware endpoints 9/13, PN capture, DBPSK, full error-correction chain, sampled complex channel,
  CRC, actual receive bytes and diagnostics.
- ARM: fourteen virtual UAV nodes, scenario parameters, deterministic trajectories, queues, fixed routing,
  TDMA, bounded retransmission, execution of simulator commands.
- PC: configuration, serial ownership, presentation, evidence and optional local Q&A.
- Preserve `docs/baseline.json`. Do not overwrite the accepted fallback directory.

## Workflow

1. Read `docs/product_contract.txt`, `configs/default.json` and `docs/progress.json`.
2. For a new preset, update the independent Python reference and ARM calculation;
   validate ranges, continuous geometry, replay seed and quantization explicitly.
3. Run `tests/product_scene_acceptance.py` without `--board` for independent checks.
4. Rebuild ARM with `tools/rebuild_product.ps1`. For FPGA changes also rebuild with
   `hw/build_verified_entry.tcl` and inspect setup/hold/DRC/resource reports.
5. Run RTL positive and negative receive tests before putting new logic on board.
6. Program matching BIT, PS initialization and ELF using `program_run.tcl`.
7. Run scene, payload, command, receiver-range and complete-network tests. Check
   originals returned over UART, never repair failed data from the transmit copy.
8. Run the current exact image three times; include stop/restart and fault recovery.
9. Only then freeze hashes, resources, timing, runtime memory, full duration and
   delivery/timeliness evidence. A passing old build does not certify a new build.

## AI prompt and correction record

The task was to complete a single-board product, preserve compliance and place UI
redesign last. The implementation instructions required source ownership boundaries,
honest display of physical versus virtual nodes, actual FPGA receive results,
deadline-aware metrics, and reversible, user-confirmed simulator commands.

Corrections made during this iteration:

- Removed a stale 50 MHz register-document value; current accepted clock was 62.5 MHz.
- Kept the 2025 aggregate finalist ratio separate from an unknown 2026 AMD-junior rate.
- Added two independent board-internal FPGA endpoints under the agreed single-board acceptance scope; external second-board verification remains deferred. Injection alone is not hardware endpoint evidence.
- Added a frame-energy-per-payload-bit comparison; equal sample SNR alone is not coding gain.
- Added explicit atomic scene configuration, immutable run configuration and per-run identifiers.
- Kept failed capture, CRC failure, missing ACK, queue rejection, expiration and backlog visible.
- Identified that passive advice can work without an LLM; optional model text cannot execute commands.

The live decision log and test transcripts are the evidence for further corrections.
Do not describe unfinished features as accepted. Preserve third-party notices and
software/model provenance when preparing the final open-source release.
