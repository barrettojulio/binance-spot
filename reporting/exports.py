def export_weekly(persistence, lane_decisions, allocation, rows, eligible):
    # eligible extended with allocation amounts
    el = [(s, sc, next((amt for ss, amt in allocation['top_allocations'] if ss==s), 0.0)) for s, sc in eligible]
    persistence.export_snapshot("weekly", rows, eligible=el, allocation=allocation)
