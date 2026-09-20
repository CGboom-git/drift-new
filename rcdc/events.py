"""Host-owned evidence and feedback identity; external strings have no authority."""
import json
from .schema import Evidence, canonical, digest


class EvidenceLedger:
    def __init__(self, task_id):
        self.task_id = task_id
        self.epoch = 0
        self.revision = 0
        self._evidence = []
        self._calls = {}
        self.ambiguous_ids = set()

    def reset(self):
        self.epoch += 1
        self.revision += 1
        self._evidence.clear()
        self._calls.clear()
        self.ambiguous_ids.clear()

    def observe_call(self, call):
        if call.task_id != self.task_id or call.epoch != self.epoch:
            raise ValueError('cross_task_or_attempt_call')
        previous = self._calls.get(call.call_id)
        if not call.call_id or (previous is not None and previous != call):
            self.ambiguous_ids.add(call.call_id)
        self._calls[call.call_id] = call

    def record_response(self, call, payload, position, success=True):
        self.observe_call(call)
        if position <= call.position:
            raise ValueError('response_before_call')
        if any(e.call_id == call.call_id for e in self._evidence):
            self.ambiguous_ids.add(call.call_id)
        self.revision += 1
        e = Evidence(self.task_id, f'rcvr_source_{self.epoch}_{self.revision}', call.call_id,
                     call.tool, call.arguments, canonical(payload), position, self.epoch, success, self.revision)
        self._evidence.append(e)
        return e

    def evidence(self):
        return tuple(self._evidence)


class HostFeedbackRegistry:
    def __init__(self):
        self._messages = {}

    def issue(self, payload):
        message = {'role': 'user', 'content': canonical({'type': 'rcvr_host_control', **payload})}
        self._messages[id(message)] = (message, digest(message))
        return message

    def authentic(self, message):
        entry = self._messages.get(id(message))
        return bool(entry and entry[0] is message and entry[1] == digest(message))

    def reset(self):
        self._messages.clear()
