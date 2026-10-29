import os
import secrets
import hashlib
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from dashboard.client import FeatureClient, DashboardError
from dashboard.data import GROUPS, dataset_export, feature_columns, public_frame, quality, subject_alias

load_dotenv('.env' if os.getenv('APP_MODE') == 'live' else '.env.demo')
st.set_page_config(page_title='Driving Simulator Physiological Data Management & Processing', page_icon='◈', layout='wide')
st.markdown('''<style>
    .block-container {max-width:1440px;padding-top:2rem;padding-bottom:3rem;}
    [data-testid="stMetric"] {background:#f0f5f9;border:1px solid #dbe5ed;
      border-radius:10px;padding:16px;}
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {color:#142b43;}
    h1,h2,h3 {letter-spacing:-.025em;}
    @media(max-width:700px){.block-container{padding:1rem;}}
    </style>''', unsafe_allow_html=True)


@st.cache_resource
def settings():
    return {'mode': os.getenv('DASHBOARD_MODE', 'demo'),
            'salt': os.getenv('DASHBOARD_ALIAS_SECRET') or secrets.token_hex(32)}


@st.cache_data(ttl=60, show_spinner=False)
def read_data(kind, mode, patient=None, scenario=None, label=None, limit=25, offset=0):
    client = FeatureClient(mode=mode)
    if kind == 'stats':
        return client.stats()
    if kind == 'page':
        return client.page(patient, scenario, label, limit, offset)
    return client.dataset(patient, scenario, label)


def distribution(counts, title):
    st.subheader(title)
    frame = pd.DataFrame({'Category': list(counts), 'Records': list(counts.values())})
    if not frame.empty:
        st.bar_chart(frame, x='Category', y='Records', color='#206f91', use_container_width=True)
        st.dataframe(frame, hide_index=True, use_container_width=True)


def main():
    config = settings()
    mode, salt = config['mode'], config['salt']
    with st.sidebar:
        st.header('Driving data workspace')
        st.caption('FEATURE DATA WORKSPACE')
        page = st.radio('Workspace', ['Overview', 'Feature Explorer', 'Data Quality', 'Dataset Export'])
        st.divider()
        st.caption('Synthetic portfolio demo' if mode == 'demo' else 'Private research workspace')
        if st.button('Refresh data', use_container_width=True):
            read_data.clear()
        st.caption('Read-only workspace · cached for up to 60 seconds')
    st.title(page)
    if mode == 'demo':
        st.info('Synthetic demonstration data — all subjects, measurements and labels are fictional.')
    else:
        st.warning('Private research data. Display aliases do not make measurements safe for public sharing.')
    try:
        if page == 'Overview':
            stats = read_data('stats', mode)
            a, b, c = st.columns(3)
            a.metric('Scenario records', f"{stats['total']:,}")
            b.metric('Scenario types', len(stats['scenarios']))
            c.metric('Label categories', len(stats.get('labels') or {}))
            left, right = st.columns(2)
            with left:
                distribution(stats['scenarios'], 'Scenario distribution')
            with right:
                distribution(stats.get('labels') or {}, 'Label distribution')
            st.caption('Each record represents one scenario observation; records are not unique participants.')
            return

        # Only aggregate metadata, aliases and selected feature values are sent
        # to Streamlit elements; raw HTTP payloads remain server-side.
        dataset = read_data('dataset', mode)
        col1, col2, col3 = st.columns(3)
        aliases = {subject_alias(p, salt): p for p in sorted(dataset.id_anonymat.dropna().unique())}
        selected_subject = col1.selectbox('Subject', ['All subjects'] + sorted(aliases))
        scenario = col2.selectbox('Scenario', ['All scenarios'] + sorted(dataset.id_scenario.dropna().unique()))
        label = col3.selectbox('Label', ['All labels'] + sorted(dataset.label.dropna().unique()))
        patient = aliases.get(selected_subject)
        scenario = None if scenario == 'All scenarios' else scenario
        label = None if label == 'All labels' else label
        frame = dataset
        for column, value in [('id_anonymat', patient), ('id_scenario', scenario), ('label', label)]:
            if value is not None:
                frame = frame[frame[column] == value]

        if page == 'Feature Explorer':
            a, b = st.columns(2)
            limit = a.selectbox('Records per page', [10, 25, 50, 100], index=1)
            # A filter-specific widget resets pagination on every filter change.
            scope = hashlib.sha256(f'{patient}:{scenario}:{label}:{limit}'.encode()).hexdigest()
            pages = max(1, (len(frame) + limit - 1) // limit)
            index = b.number_input('Page', min_value=1, max_value=pages, value=1, step=1, key='page-' + scope)
            total, records = read_data('page', mode, patient, scenario, label, limit, (index - 1) * limit)
            st.caption(f'{total:,} matching records · page {index} of {pages}')
            if records.empty:
                st.info('No records match these filters.')
                return
            table = public_frame(records, salt)
            table['Available features'] = records[feature_columns(records)].notna().sum(axis=1)
            st.dataframe(table[['Subject', 'Scenario', 'Label', 'Available features']], hide_index=True,
                         use_container_width=True)
            selected = st.selectbox('Inspect observation on this page', list(range(len(records))),
                                    format_func=lambda i: f"Observation {i + 1} · {table.iloc[i]['Subject']} · {table.iloc[i]['Scenario']}")
            row = records.iloc[selected]
            details = pd.DataFrame({'Feature': feature_columns(records),
                                    'Value': [row[c] for c in feature_columns(records)]})
            st.subheader('Feature details')
            st.dataframe(details, hide_index=True, use_container_width=True)

        elif page == 'Data Quality':
            if frame.empty:
                st.info('No records match these filters. Quality rates are unavailable.')
                return
            report = quality(frame)
            a, b, c, d = st.columns(4)
            a.metric('Records assessed', report['records'])
            b.metric('Feature fields', report['feature_fields'])
            c.metric('Missing cells', f"{report['missing_percent']:.1f}%" if report['missing_percent'] is not None else '—')
            d.metric('Invalid values', report['invalid_cells'])
            st.caption('Missing rate = empty feature cells / all selected record × feature cells. '
                       'Scenario-specific fields and unavailable modalities can be empty by design; this is not a clinical quality score.')
            st.subheader('Modality availability')
            modalities = report['modalities']
            st.bar_chart(modalities.set_index('Modality')[['Availability (%)']], color='#206f91')
            st.dataframe(modalities, hide_index=True, use_container_width=True)
            st.caption('Availability means at least one finite numerical feature in an eligible record. '
                       'Driving simulator eligibility excludes scenario_5. Other modalities include all selected records.')
            st.subheader('Missing values by feature')
            st.dataframe(report['features'].sort_values('Missing (%)', ascending=False),
                         hide_index=True, use_container_width=True)
            st.write(f"{report['all_missing_fields']} entirely missing fields · "
                     f"{report['records_without_values']} records without numerical values · "
                     f"{report['duplicate_record_ids']} repeated record IDs")

        elif page == 'Dataset Export':
            st.subheader('Build a feature dataset')
            groups = st.multiselect('Feature groups', list(GROUPS), default=list(GROUPS),
                                    format_func=lambda g: f'{g} · {GROUPS[g]}')
            include_subject = st.checkbox('Include anonymous subject grouping key', value=False,
                                          help='Useful for separating subjects in downstream datasets. Source participant IDs are always excluded.')
            exported = dataset_export(frame, groups, include_subject, salt)
            a, b = st.columns(2)
            a.metric('Export records', len(exported))
            b.metric('Export feature fields', max(0, len(exported.columns) - 2 - int(include_subject)))
            if not groups or frame.empty:
                st.info('Select a feature group and filters with matching records to export.')
                return
            st.dataframe(exported.head(10), hide_index=True, use_container_width=True)
            name = 'synthetic_features.csv' if mode == 'demo' else 'private_research_features.csv'
            st.download_button('Download CSV', exported.to_csv(index=False).encode('utf-8'),
                               file_name=name, mime='text/csv', use_container_width=True)
            st.caption('Original feature names and values are retained. Missing values remain blank; no imputation or model training is performed.')
    except DashboardError as exc:
        st.error(str(exc))
    except Exception:
        # Never render raw upstream exceptions, HTTP requests, or record payloads.
        st.error('This view could not be loaded. Refresh or check the dashboard service configuration.')


main()
