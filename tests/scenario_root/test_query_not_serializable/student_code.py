class Thing:
    pass


x = Thing()
y = 5
nested = [1, {"thing": Thing()}]
self_reference = [1]
self_reference.append(self_reference)
