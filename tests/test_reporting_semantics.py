"""Changed-data reporting checks; no committed reports or data are written."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

from keeta_voc import facts

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def results(monkeypatch):
    data = copy.deepcopy(facts.load_results())
    monkeypatch.setattr(facts, 'load_results', lambda: data)
    return data


@pytest.mark.parametrize('rules,llm,primary,phrase', [
    (.4, .9, 'llm', 'LLM micro-F1 is higher'),
    (.9, .4, 'rules', 'LLM micro-F1 is lower'),
    (.7, .7, 'rules', 'equal micro-F1'),
    (None, None, 'rules', 'cannot be estimated'),
    (float('nan'), .7, 'rules', 'cannot be estimated'),
])
def test_both_documents_report_actual_method_comparison(results, rules, llm, primary, phrase):
    q, m = results['quality'], results['metrics']
    q['rules']['overall']['micro_f1'] = rules
    q['llm']['overall']['micro_f1'] = llm
    m['primary_method'], m['secondary_method'] = primary, 'rules' if primary == 'llm' else 'llm'
    q['llm_minus_rules']['micro_f1'] = {'diff': None, 'ci': [None, None]}
    docs = script('check_numbers').render_all()
    for text in docs.values():
        assert phrase in text
        assert f'Primary labeler recorded in metrics: **{primary}**' in text
        assert 'scored **higher** than a local LLM' not in text
        assert ' nan' not in text.lower()
    assert f'主结果记录使用：{primary}' in docs['README.md']


@pytest.mark.parametrize('ci,phrase', [([-.1, .2], 'includes zero'), ([0, .2], 'includes zero'),
                                      ([.1, .2], 'supports higher'), ([-.2, -.1], 'supports lower'),
                                      ([None, .2], 'interval is unavailable')])
def test_difference_claims_require_the_actual_paired_interval(results, ci, phrase):
    results['quality']['llm_minus_rules']['micro_f1'] = {'diff': .1, 'ci': ci}
    docs = script('check_numbers').render_all()
    assert phrase in docs['REPORT.md']
    assert 'statistically tied' not in docs['REPORT.md']


def test_partial_label_interval_does_not_claim_a_win(results):
    results['quality']['llm_minus_rules']['delivery_time'] = {'diff': .2, 'ci': [.1, None]}
    assert 'Delivery time' not in facts.build_context()['words']['llm_wins']
    assert 'n/a' in facts.table_quality()


def test_no_estimable_primary_label_f1_is_rendered_honestly(results):
    for row in results['quality']['rules']['per_label'].values():
        row['f1'] = None
        row['f1_ci'] = [None, None]
    assert 'Per-label F1 is unavailable' in script('check_numbers').render_all()['REPORT.md']


def test_limitations_describe_the_primary_labeler_instead_of_always_rules(results):
    results['metrics'].update(primary_method='llm', secondary_method='rules')
    for row in results['quality']['llm']['per_label'].values():
        row['f1'] = .11
    report = script('check_numbers').render_all()['REPORT.md']
    assert 'primary labeler (llm) has estimable per-label F1 from 0.11' in report


def test_secondary_rankings_apply_their_own_eligible_denominator(results):
    for row in results['metrics']['pain_point_intervals']['llm']['ae'].values():
        row['n_negative'] = 29
    ctx = facts.build_context()
    assert 'UAE' in ctx['words']['rank1_primary_summary']
    assert 'UAE' not in ctx['rank1_sec_summary']


def test_no_eligible_markets_remains_a_readable_report(results):
    for method in ('rules', 'llm'):
        for rows in results['metrics']['pain_point_intervals'][method].values():
            for row in rows.values():
                row['n_negative'] = 29
    report = script('check_numbers').render_all()['REPORT.md']
    assert 'no eligible markets' in report
    assert 'UAE: too few' in report


def test_no_customer_service_first_place_is_valid(results):
    for rows in results['metrics']['pain_point_intervals']['rules'].values():
        for label, row in rows.items():
            row['rank'] = 1 if label == 'delivery_time' else 2
    report = script('check_numbers').render_all()['REPORT.md']
    assert '0 of\n   6 markets' in report
    assert 'customer service leads everywhere' not in report


def test_skipped_recent_period_and_reversed_trend_do_not_keep_old_findings(results):
    recent = results['metrics']['recent_change']['rules']
    recent['ae'] = {'recent_month': '2026-09', 'base_months': ['2026-08'], 'n_recent': 2,
                    'n_base': 20, 'skipped': 'fewer than 30 reviews in one period'}
    recent['sa']['negative'].update(recent=.98, base=.50, diff=.48, diff_ci=[.3, .6])
    docs = script('check_numbers').render_all()
    assert 'UAE: recent comparison unavailable' in docs['REPORT.md']
    assert 'Saudi Arabia' in docs['REPORT.md'] and '+48 pp' in docs['REPORT.md']
    for text in docs.values():
        assert 'did not move' not in text
        assert 'share of written reviews fell' not in text
        assert '并列第一' not in text


def dashboard_dom(html):
    # Execute the generated JavaScript, keeping just the DOM in memory.
    program = r'''
const fs = require('node:fs'), vm = require('node:vm');
const html = fs.readFileSync(0, 'utf8');
class El {
  constructor(tag='div') { this.tag=tag; this.children=[]; this.style={}; this.attrs={}; this.innerHTML=''; this.textContent=''; }
  appendChild(child) { this.children.push(child); }
  setAttribute(k,v) { this.attrs[k]=v; }
  addEventListener() {}
}
const els = new Map();
vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], {document: {
 getElementById(id) { if(!els.has(id)) els.set(id,new El()); return els.get(id); },
 createElement: tag=>new El(tag), createElementNS: (_,tag)=>new El(tag)
}, window: {innerWidth:1280}});
console.log(JSON.stringify(els.get('pain').children.map(c=>({heading:c.innerHTML,
 text:c.children.map(x=>x.textContent).join(' '), charts:c.children.filter(x=>x.tag==='svg').length}))));
'''
    completed = subprocess.run(['node', '-e', program], input=html, text=True, encoding='utf-8',
                               capture_output=True, check=True)
    return json.loads(completed.stdout)


@pytest.mark.parametrize('n,charts', [(9, 0), (29, 0), (30, 1)])
def test_dashboard_uses_the_same_small_sample_boundary_as_report(results, n, charts):
    for row in results['metrics']['pain_point_intervals']['rules']['om'].values():
        row['n_negative'] = n
        row['share'] = row['n_label'] / n
    cards = dashboard_dom(script('build_dashboard').build())
    oman = next(c for c in cards if '<h3>Oman</h3>' in c['heading'])
    assert oman['charts'] == charts
    if not charts:
        assert 'Too few' in oman['text']
        assert str(facts.MIN_STOREFRONT_NEG) in oman['text']
    assert any(c['charts'] == 1 for c in cards if '<h3>UAE</h3>' in c['heading'])


def test_dashboard_empty_market_and_missing_quality_estimate_do_not_crash(results):
    results['metrics']['pain_point_intervals']['rules']['om'] = {}
    for method in ('rules', 'llm'):
        results['quality'][method]['overall']['micro_f1'] = None
        results['quality'][method]['overall']['micro_f1_ci'] = [None, None]
    cards = dashboard_dom(script('build_dashboard').build())
    oman = next(c for c in cards if '<h3>Oman</h3>' in c['heading'])
    assert oman['charts'] == 0 and 'Too few' in oman['text']


def test_templates_keep_numeric_claims_as_placeholders():
    check = script('check_numbers')
    for template, _ in check.DOCS:
        text = (ROOT / template).read_text(encoding='utf-8')
        assert [(line, number) for line, number in check.literal_numbers(text)
                if number not in check.ALLOWED_LITERALS] == []
