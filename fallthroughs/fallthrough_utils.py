def add_child(parent, child):
    child.parent = parent
    parent.children.append(child)
