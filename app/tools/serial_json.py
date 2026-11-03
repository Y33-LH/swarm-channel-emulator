"""Strict framing; optional firmware-negotiated, CRC checked replay of one RPC.

Legacy commands are never retried. Protected requests use an identical request
ID and body: firmware returns the cached reply without re-executing the action.
"""
import json
import time
import secrets
import zlib
from network_wire import expand_network


class SerialResponseError(RuntimeError):
    def __init__(self, detail):
        self.detail = detail
        super().__init__(f"Serial response {detail['reason']}; command={detail['command']!r}; "
                         f"received={detail['received_bytes']} bytes; incomplete={detail['partial_bytes']} bytes. "
                         "Session stopped. Protected retries, if used, replay the same request ID without executing it again.")


class JsonSerial:
    """One outstanding request. A timeout/corruption poisons the session to avoid stale replies."""
    def __init__(self, port, on_error=None, clock=time.monotonic, max_line=32768):
        self.port = port
        self.on_error = on_error
        self.clock = clock
        self.max_line = max_line
        self.buffer = bytearray()
        self.failed = False
        self.protected = False
        self.request_id = secrets.randbelow(0xfffffffe)+1
        self.recoveries = []

    def request(self, command, timeout=5):
        if self.failed:
            raise RuntimeError('Serial session needs reconnect after previous response failure; no command sent.')
        if not self.protected:
            obj = self._exchange(command, timeout)
            if command == 'PING' and obj.get('transport') == 'crc32-replay-v1':
                self.protected = True
            return obj
        if timeout <= 0 or '\n' in command or '\r' in command:
            raise ValueError('Invalid command or deadline')
        self.request_id = self.request_id % 0xffffffff+1
        rid = self.request_id
        raw = command.encode('ascii')
        wire = f'Q {rid} {zlib.crc32(raw):08x} {command}'
        attempts=[]
        callback=self.on_error
        try:
            self.on_error=None
            for attempt in range(3):
                try:
                    obj=self._exchange(wire, timeout, request_id=rid)
                    if attempts:self.recoveries.append(dict(command=command,request=rid,failures=attempts))
                    return obj
                except SerialResponseError as error:
                    attempts.append(error.detail)
                    if error.detail['reason'] not in ('invalid_complete_json','invalid_compact_telemetry','invalid_transport',
                            'deadline_without_complete_response','line_too_long') or attempt==2:
                        error.detail.update(logical_command=command,protected_replay=True,attempts=attempts[:-1])
                        if callback:callback(error.detail)
                        raise
                    # No following logical command has been sent. Discard only
                    # damaged input and replay this exact firmware-cached RPC.
                    self.buffer.clear()
                    if hasattr(self.port,'reset_input_buffer'):self.port.reset_input_buffer()
                    self.failed=False
        finally:
            self.on_error=callback

    def _exchange(self, command, timeout=5, request_id=None):
        if self.failed:
            raise RuntimeError('Serial session needs reconnect after previous response failure; no command sent.')
        if timeout <= 0 or '\n' in command or '\r' in command:
            raise ValueError('Invalid command or deadline')
        wire = (command+'\n').encode('ascii')
        started = self.clock()
        deadline = started+timeout
        received = bytearray()
        offending_line = b''
        original_timeout = self.port.timeout
        reason = 'io_error'
        try:
            sent = self.port.write(wire)
            if sent != len(wire):
                reason = 'short_write'
                raise OSError('Incomplete serial command write')
            self.port.flush()
            while True:
                remaining = deadline-self.clock()
                if remaining <= 0:
                    reason = 'deadline_without_complete_response'
                    raise TimeoutError('No complete newline-terminated JSON response before deadline')
                end = self.buffer.find(b'\n')
                if end >= 0:
                    if end+1 > self.max_line:
                        reason = 'line_too_long'
                        raise ValueError('Response exceeds line limit')
                    offending_line = bytes(self.buffer[:end+1])
                    del self.buffer[:end+1]
                    if not offending_line.strip():
                        continue
                    payload=offending_line.rstrip(b'\r\n')
                    if request_id is not None:
                        reason='invalid_transport'
                        if not payload.startswith(b'@'):raise ValueError('Missing protected response header')
                        ident,size,crc,payload=payload[1:].split(b':',3)
                        if int(ident)!=request_id:raise ValueError('Stale response request identity')
                        if int(size)!=len(payload):raise ValueError('Response length mismatch')
                        if len(crc)!=8 or int(crc,16)!=zlib.crc32(payload):raise ValueError('Response CRC mismatch')
                    reason = 'invalid_complete_json'
                    obj = json.loads(payload.decode('ascii'))
                    if not isinstance(obj, dict):
                        raise ValueError('Response must be a JSON object')
                    # Only this explicitly defined unsolicited startup message is skipped.
                    if obj.get('type') == 'READY':
                        offending_line = b''
                        continue
                    if 'transport_error' in obj:
                        reason='invalid_transport' if obj['transport_error']=='REQUEST_CRC' else 'transport_rejected'
                        raise ValueError(obj['transport_error'])
                    reason = 'invalid_compact_telemetry'
                    return expand_network(obj)
                if len(self.buffer) >= self.max_line:
                    reason = 'line_too_long'
                    raise ValueError('Response exceeds line limit without newline')
                # pyserial read_until may return a partial line on *each* timeout.
                # Preserve every byte until LF or the transaction deadline; do not resend.
                self.port.timeout = min(original_timeout if original_timeout and original_timeout > 0 else .2, remaining)
                reason = 'io_error'
                # Read a USB/UART batch rather than issuing one Windows read
                # per byte. The newline parser above remains the sole framing
                # authority, including partial lines and unsolicited READY.
                available = self.port.in_waiting
                chunk = self.port.read(min(max(1, available), self.max_line-len(self.buffer)))
                self.buffer.extend(chunk)
                received.extend(chunk)
        except Exception as e:
            self.failed = True
            detail = dict(command=command, reason=reason, error=str(e), elapsed_s=self.clock()-started,
                          received_bytes=len(received), partial_bytes=len(self.buffer),
                          received_hex=received[:self.max_line*2].hex(),
                          partial_hex=bytes(self.buffer[:self.max_line]).hex(),
                          offending_line_hex=offending_line[:self.max_line].hex())
            if self.on_error:
                try: self.on_error(detail)
                except Exception as log_error: detail['diagnostic_write_error'] = str(log_error)
            raise SerialResponseError(detail) from e
        finally:
            self.port.timeout = original_timeout
