from o_event.models import Run, Status, Competitor

from typing import List, Tuple
from dataclasses import dataclass


class Ranking:
    def rank(self, runs: list[Run]) -> list[(int, int, Run)]:
        # Ranking: OK runners only, sorted by result
        ok_runs = [r for r in runs if r.status == Status.OK]
        ok_runs_sorted = sorted(ok_runs, key=lambda r: r.result if r.result is not None else -1)
        dsq_runs = [r for r in runs if r.status != Status.OK]
        dsq_runs_sorted = sorted(dsq_runs, key=lambda r: r.result if r.result is not None else -1)

        best_time = ok_runs_sorted[0].result if ok_runs_sorted else None

        ranks = []

        position = 1
        prev_time_behind = 0

        for i, run in enumerate(ok_runs_sorted, 1):
            time_behind = run.result - best_time
            if prev_time_behind != time_behind:
                position = i
            ranks.append((position, time_behind, run))

        for run in dsq_runs_sorted:
            ranks.append((None, None, run))

        return ranks

    @dataclass
    class Result:
        competitor: Competitor
        scores: List[int]
        best_count: int
        total_score: int
        total_time: int

    def rank_multiday(
        self,
        days_to_calculate: int,
        competitors: List[Competitor],
    ) -> Tuple[int | None, Result]:
        """
        Returns list of (place, [scores per day], competitor).
        Sorted by:
           1) number of OK stages used for scoring (3 best)
           2) sum of scores
           3) sum of times (lower is better)
        """

        # -------------------------------------------
        # 1) Group runs day→[run] and determine winners per day
        # -------------------------------------------
        runs_by_day = {day: [] for day in range(1, days_to_calculate + 1)}

        for c in competitors:
            for r in c.runs:
                if 1 <= r.day <= days_to_calculate:
                    runs_by_day[r.day].append(r)

        # winners (fastest OK run) needed to compute "time behind"
        winners = {}  # day → fastest time
        for day, runs in runs_by_day.items():
            ok_times = [r.result for r in runs if r.status == Status.OK and r.result is not None]
            winners[day] = min(ok_times) if ok_times else None

        # -------------------------------------------
        # 2) Compute score for each run
        # -------------------------------------------
        def score_for_run(run: Run) -> int:
            if run.status != Status.OK:
                return 0
            winner_time = winners.get(run.day)
            if not winner_time:
                return 0  # no winner that day

            time = run.result
            time_behind = time - winner_time

            s = int(100 * (2.0 - time_behind / (time - time_behind)))
            return s if s >= 0 else 0

        # -------------------------------------------
        # 3) Build competitor aggregated performance
        # -------------------------------------------
        aggregated: List[Ranking.Result] = []

        for c in competitors:
            # Collect runs in order of day
            runs = {r.day: r for r in c.runs if 1 <= r.day <= days_to_calculate}

            scores = []
            used_runs = []

            for day in range(1, days_to_calculate + 1):
                run = runs.get(day)
                if run:
                    s = score_for_run(run)
                    scores.append(s)
                    used_runs.append(run)
                else:
                    scores.append(0)

            # sort runs by score desc + time asc
            ok_runs_sorted = sorted(
                [r for r in used_runs if r.status == Status.OK],
                key=lambda r: (score_for_run(r), - (r.result or 9999999)),
                reverse=True,
            )

            # Take 3 best
            best = ok_runs_sorted[:3]

            total_score = sum(score_for_run(r) for r in best)
            total_time = sum(r.result for r in best) if best else None

            aggregated.append(Ranking.Result(c, scores, len(best), total_score, total_time))

        # -------------------------------------------
        # 4) Sort by:
        #       best_count desc,
        #       total_score desc,
        #       total_time asc
        # -------------------------------------------
        aggregated.sort(
            key=lambda a: (a.best_count, a.total_score, -(a.total_time or 9999999)),
            reverse=True
        )

        # -------------------------------------------
        # 5) Assign places (with ties)
        # -------------------------------------------
        results = []
        place = 1

        for idx, a in enumerate(aggregated):
            key = (a.best_count, a.total_score, a.total_time)
            if idx > 0 and key != aggregated[idx - 1]:
                place = idx + 1

            results.append((place if a.best_count > 0 else None, a))

        return results
