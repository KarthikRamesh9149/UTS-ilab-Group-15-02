"""Whole-variant C0/C1/C2/C3 ranking; never a per-task best-of score."""
from deadline_custom_policy import cells, fingerprint, parent_selection, summary_fields
from portable_final_selection import checked, ranked, select as previous_select, diagnostic


def checked_c3(summary, parent_document):
    summary_fields(summary,c3=True)
    parent=parent_selection(parent_document)
    selected=parent['selected']
    if (not isinstance(summary,dict) or summary.get('parent')!=selected
            or summary.get('base_parent')!=parent['custom_parent']):
        raise ValueError('C3 must retain its preselected parent lineage')
    tasks=[row.get('task_id') for row in summary.get('rows',[]) if isinstance(row,dict)]
    row=checked(summary,'C3',expected_cells=cells(tasks),
        complexity=parent['summaries'][selected]['complexity']+1)
    return dict(row,base_parent=parent['custom_parent'])


def select(summaries,parent_document):
    if not isinstance(summaries,dict) or set(summaries)!={'C0','C1','C2','C3'}:
        raise ValueError('All four complete audited development blocks required')
    old={c:summaries[c] for c in ('C0','C1','C2')}
    if fingerprint(old)!=fingerprint(parent_document.get('summaries')):
        raise ValueError('Predecessor results changed since C3 parent selection')
    parent=parent_selection(parent_document);previous=previous_select(old)
    rows=dict(previous['summaries'],C3=checked_c3(summaries['C3'],parent_document))
    winner,complete_costs=ranked(rows)
    if winner=='C3':
        # The C3 revision contains several explicitly authorised changes. Its
        # whole-parent comparison is not an isolated mechanism attribution.
        comparison=dict(kind='combined_revision_parent_comparison',condition=parent['selected'],
            parent=parent['custom_parent'],causal_single_lever_claim=False)
        lineage=dict(parent=parent['selected'],base_parent=parent['custom_parent'])
    else:
        comparison=diagnostic(rows,winner,rows[winner]['parent'])
        lineage=dict(parent=rows[winner]['parent'],base_parent=None)
    return dict(kind='four_variant_selection_not_execution_admission',selected=winner,**lineage,
        summaries=rows,total_development_attempts=80,cost_tiebreak_used=complete_costs,
        diagnostic=comparison,primary_comparator='terminus-2',secondary_comparator='openhands',
        efficiency_win_claimed=False,full_benchmark_win_claimed=False,paid_launch_ready=False)
