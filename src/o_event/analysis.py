from typing import TypeAlias, List, Tuple
from dataclasses import dataclass


ControlTime: TypeAlias = Tuple[int, int]
ControlList: TypeAlias = List[ControlTime]
IdxPair: TypeAlias = Tuple[int, int]
IntList: TypeAlias = List[int]


class Analysis:

    def __init__(self):
        ...

    @dataclass
    class Result:
        visited: ControlList
        missing: IntList
        extra: ControlList
        all_visited: bool
        order_correct: bool
        matches_raw: List[IdxPair]

    def analyse_order(self, required: IntList, punches: ControlList) -> Result:
        """
        required: [control codes]
        punches:  [(code, time), ...]
        """

        n = len(required)
        m = len(punches)

        # dp[i][j] = best match count for required[:i] and punches[:j]
        dp = [[0] * (m + 1) for _ in range(n + 1)]

        # For backtracking
        parent = [[None] * (m + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            r = required[i - 1]
            for j in range(1, m + 1):
                c, _ = punches[j - 1]

                # Option A: skip punch j
                best = dp[i][j - 1]
                parent_choice = ("left", i, j - 1)

                # Option B: skip required i
                if dp[i - 1][j] > best:
                    best = dp[i - 1][j]
                    parent_choice = ("up", i - 1, j)

                # Option C: match
                if r == c:
                    if dp[i - 1][j - 1] + 1 > best:
                        best = dp[i - 1][j - 1] + 1
                        parent_choice = ("diag", i - 1, j - 1)

                dp[i][j] = best
                parent[i][j] = parent_choice

        # Backtrack to get matches
        matches = []
        i, j = n, m
        while i > 0 and j > 0:
            direction, pi, pj = parent[i][j]

            if direction == "diag" and required[i - 1] == punches[j - 1][0]:
                # A match
                matches.append((i - 1, j - 1))  # store (required index, punch index)
                i, j = pi, pj
            else:
                i, j = pi, pj

        matches.reverse()

        # Extract info
        used_req = {ri for (ri, pj) in matches}
        used_punch = {pj for (ri, pj) in matches}

        visited = [(required[ri], punches[pj][1]) for (ri, pj) in matches]
        missing = [required[i] for i in range(n) if i not in used_req]
        extra = [punches[j] for j in range(m) if j not in used_punch]

        # Order correctness
        # - If all required controls matched, the order is correct.
        # - DP guarantees index monotonicity.
        all_visited = (len(matches) == n)
        order_correct = all_visited

        # Build "visited" with times or None
        visited = []
        for req_i, code in enumerate(required):
            match = next((pj for (ri, pj) in matches if ri == req_i), None)
            if match is None:
                visited.append((code, None))
            else:
                visited.append((code, punches[match][1]))

        return Analysis.Result(visited, missing, extra, all_visited, order_correct, matches)
