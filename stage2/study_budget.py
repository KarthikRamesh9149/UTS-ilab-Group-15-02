"""Netcup budget amendment, authorised 19 September 2026 before scored work.

All conditions share the same estimated trial cap. The durable ledger retains
full-context reservations globally, a two-dollar account reserve, and fail-closed
reconciliation. Existing ledgers with another policy are never migrated silently.
"""
TRIAL_CAP = '0.023'
SCORED_CEILING = '8.901'
STAGE_CAPS = {'development': '2.760', 'final': '6.141'}
SETUP_CAP = '1.00'  # Original shared ledger, including prior setup spending.
ACCOUNT_RESERVE = '2.00'
