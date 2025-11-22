from o_event.models import Run, Status


class Ranking:
    def rank(self, runs: list[Run]) -> list[(int, int, Run)]:
        # Ranking: OK runners only, sorted by result
        ok_runs = [r for r in runs if r.status == Status.OK]
        ok_runs_sorted = sorted(ok_runs, key=lambda r: r.result)
        dsq_runs = [r for r in runs if r.status != Status.OK]
        dsq_runs_sorted = sorted(dsq_runs, key=lambda r: r.result)

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
