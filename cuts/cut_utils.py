from typing import List


def merge_groups(groups: List[set], a: str, b: str) -> List[set]:
    # Used to detect pairwise unreachable nodes
    # As per Robust Process Mining with Guarantees
    # S. Leemans
    group_A, group_B = None, None
    for group in groups:
        if a in group:
            group_A = group
        if b in group:
            group_B = group
    if group_A is not None and group_B is not None and group_A != group_B:
        groups.remove(group_A)
        groups.remove(group_B)
        merged_group = group_A.union(group_B)
        groups.append(merged_group)
    return groups
