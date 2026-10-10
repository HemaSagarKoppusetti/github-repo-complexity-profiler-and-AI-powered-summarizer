# app.py
# Streamlit dashboard — wires all 7 core modules into one UI.

import os
import streamlit as st
from core.cloner import clone_repo, cleanup_repo
from core.scanner import scan_repo
from core.complexity import analyse_all
from core.churn import analyse_churn
from core.graph import build_dependency_graph, render_graph_html
from core.hotspots import compute_hotspots
from core.summariser import generate_report

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GitHub Repo Profiler",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 GitHub Repo Complexity Profiler")
st.caption("Analyse any public GitHub repo — complexity, churn, dependencies, and AI-generated insights.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    github_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/pallets/flask",
        help="Must be a public repository"
    )
    top_n = st.slider("Top N hotspots to show", 5, 20, 10)
    run_btn = st.button("🚀 Analyse Repo", type="primary", use_container_width=True)

    st.divider()
    st.markdown("**How it works:**")
    st.markdown("""
1. 📥 Clone the repo locally
2. 🗂️ Scan all code files
3. 📊 Compute complexity (radon)
4. 🔀 Build dependency graph
5. 📈 Analyse git churn
6. 🎯 Rank hotspot risk files
7. 🤖 Generate LLM report
""")

# ── Main logic ────────────────────────────────────────────────────────────────
if run_btn:
    if not github_url.strip():
        st.error("Please enter a GitHub URL in the sidebar.")
        st.stop()

    repo_path = None

    try:
        # ── Step 1: Clone ─────────────────────────────────────────────────
        with st.status("📥 Cloning repository...", expanded=True) as status:
            result = clone_repo(github_url.strip())
            if not result["success"]:
                st.error(f"Clone failed: {result['error']}")
                st.stop()
            repo_path = result["path"]
            repo_name = result["name"]
            st.write(f"✅ Cloned **{repo_name}** to `{repo_path}`")

            # ── Step 2: Scan ──────────────────────────────────────────────
            st.write("🗂️ Scanning files...")
            manifest = scan_repo(repo_path)
            st.write(f"✅ Found **{manifest['total_files']} files** | "
                     f"**{manifest['total_loc']} LOC** | "
                     f"**{len(manifest['python_files'])} Python files**")

            # ── Step 3: Complexity ────────────────────────────────────────
            st.write("📊 Analysing complexity...")
            complexity = analyse_all(manifest["python_files"])
            c_sum = complexity["summary"]
            st.write(f"✅ {c_sum['total_functions']} functions | "
                     f"avg MI: {c_sum['avg_mi_score']}")

            # ── Step 4: Graph ─────────────────────────────────────────────
            st.write("🔀 Building dependency graph...")
            graph = build_dependency_graph(manifest["python_files"], repo_path)
            g_stats = graph["stats"]
            st.write(f"✅ {g_stats['node_count']} nodes | "
                     f"{g_stats['edge_count']} edges | "
                     f"{g_stats['cycle_count']} cycles")

            # ── Step 5: Churn ─────────────────────────────────────────────
            st.write("📈 Reading git history...")
            churn = analyse_churn(repo_path, manifest["python_files"])
            ch_stats = churn["stats"]
            st.write(f"✅ {ch_stats['total_commits']} commits | "
                     f"{ch_stats['total_authors']} authors | "
                     f"{ch_stats['repo_age_days']} days old")

            # ── Step 6: Hotspots ──────────────────────────────────────────
            st.write("🎯 Computing hotspot risk scores...")
            hotspots = compute_hotspots(complexity, churn, repo_path, top_n)
            h_sum = hotspots["summary"]
            st.write(f"✅ 🔴 {h_sum['critical_count']} critical | "
                     f"🟠 {h_sum['high_count']} high | "
                     f"🟡 {h_sum['medium_count']} medium | "
                     f"🟢 {h_sum['low_count']} low")

            # ── Step 7: LLM Report ────────────────────────────────────────
            st.write("🤖 Generating AI report (15–30s)...")
            report = generate_report(repo_name, manifest, complexity,
                                     churn, graph, hotspots)
            st.write("✅ Report generated")

            # ── Render graph HTML ─────────────────────────────────────────
            os.makedirs("reports", exist_ok=True)
            graph_path = f"reports/{repo_name}_graph.html"
            render_graph_html(graph, graph_path)

            status.update(label="✅ Analysis complete!", state="complete")

        # ── Display results ───────────────────────────────────────────────
        st.divider()

        # Row 1: key metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Files",    manifest["total_files"])
        col2.metric("Total LOC",      f"{manifest['total_loc']:,}")
        col3.metric("Total Commits",  f"{ch_stats['total_commits']:,}")
        col4.metric("Avg MI Score",   f"{c_sum['avg_mi_score']}/100")
        col5.metric("Circular Deps",  g_stats["cycle_count"],
                    delta="⚠️ found" if g_stats["cycle_count"] > 0 else "✅ none",
                    delta_color="inverse")

        st.divider()

        # Tabs for each section
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🎯 Hotspots",
            "📊 Complexity",
            "🔀 Dependency Graph",
            "📈 Churn",
            "🤖 AI Report"
        ])

        # ── Tab 1: Hotspots ───────────────────────────────────────────────
        with tab1:
            st.subheader("🎯 Hotspot Risk Ranking")
            st.caption("Risk = 50% churn + 30% complexity + 20% low maintainability")

            for f in hotspots["hotspots"]:
                tier  = f["risk_tier"]
                score = f["risk_score"]
                with st.expander(f"{tier}  `{f['rel_path']}`  — risk score: **{score}**"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Commits",      f["commit_count"])
                    c2.metric("Max CC",       f["max_cc"])
                    c3.metric("MI Score",     f["mi_score"])
                    c4.metric("Authors",      f["author_count"])
                    if f["hotspot_fn"]:
                        st.code(f"Most complex function: {f['hotspot_fn']}()")
                    if f["last_changed"]:
                        st.caption(f"Last changed: {f['last_changed']}")

        # ── Tab 2: Complexity ─────────────────────────────────────────────
        with tab2:
            st.subheader("📊 Complexity Analysis")

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**CC Rank Distribution**")
                rank_dist = c_sum["rank_distribution"]
                total_fns = c_sum["total_functions"] or 1
                for rank, count in rank_dist.items():
                    pct = count / total_fns
                    colors = {
                        "A": "🟢", "B": "🟡",
                        "C": "🟠", "D": "🔴",
                        "E": "🔴", "F": "🔴"
                    }
                    st.write(f"{colors.get(rank,'⚪')} Rank {rank}: **{count}** functions")
                    st.progress(pct)

            with col_b:
                st.markdown("**Top Complex Functions**")
                for fn in c_sum["top_complex_functions"]:
                    st.write(f"- `{fn['name']}()` — CC={fn['complexity']} "
                             f"[{fn['rank']}] line {fn['lineno']}")

            st.divider()
            st.markdown("**Per-file Maintainability Index**")
            for r in complexity["results"]:
                if r["error"]:
                    continue
                fname = os.path.basename(r["filepath"])
                mi    = r["mi_score"]
                color = "🟢" if mi >= 65 else "🟡" if mi >= 35 else "🔴"
                st.write(f"{color} `{fname}` — MI={mi} [{r['mi_rank']}]  "
                         f"avg CC={r['avg_cc']}  max CC={r['max_cc']}")
                st.progress(mi / 100)

        # ── Tab 3: Dependency Graph ───────────────────────────────────────
        with tab3:
            st.subheader("🔀 Module Dependency Graph")

            col_x, col_y = st.columns(2)
            with col_x:
                st.markdown("**Graph Stats**")
                st.write(f"- Nodes: **{g_stats['node_count']}**")
                st.write(f"- Edges: **{g_stats['edge_count']}**")
                st.write(f"- Density: **{g_stats['density']}**")
                st.write(f"- External packages: **{g_stats['external_deps']}**")

            with col_y:
                st.markdown("**Hub Modules** (most imported)")
                if graph["hub_modules"]:
                    for h in graph["hub_modules"]:
                        st.write(f"- `{h['module']}` — "
                                 f"imported by {h['imported_by']} modules")
                else:
                    st.write("None detected")

            if graph["cycles"]:
                st.error(f"⚠️ {len(graph['cycles'])} circular "
                         f"{'dependency' if len(graph['cycles'])==1 else 'dependencies'} detected!")
                for cycle in graph["cycles"]:
                    st.code(" → ".join(cycle) + f" → {cycle[0]}")
            else:
                st.success("✅ No circular dependencies found")

            st.markdown("**External Packages Referenced**")
            st.write(", ".join(f"`{p}`" for p in graph["external_packages"]))

            # Render interactive graph in iframe
            if os.path.exists(graph_path):
                with open(graph_path, "r", encoding="utf-8") as f:
                    graph_html = f.read()
                st.markdown("**Interactive Dependency Graph**")
                st.components.v1.html(graph_html, height=620, scrolling=False)

        # ── Tab 4: Churn ──────────────────────────────────────────────────
        with tab4:
            st.subheader("📈 Git Churn Analysis")

            col_p, col_q = st.columns(2)
            with col_p:
                st.markdown("**Repo Timeline**")
                st.write(f"- First commit: **{ch_stats['first_commit']}**")
                st.write(f"- Last commit:  **{ch_stats['last_commit']}**")
                st.write(f"- Repo age:     **{ch_stats['repo_age_days']} days**")
                st.write(f"- Total commits:**{ch_stats['total_commits']}**")
                st.write(f"- Contributors: **{ch_stats['total_authors']}**")

            with col_q:
                st.markdown("**Most Churned Files**")
                for f in churn["most_churned"]:
                    st.write(f"- `{f['rel_path']}` — "
                             f"**{f['commit_count']}** commits | "
                             f"{f['author_count']} author(s)")

            st.divider()
            st.markdown("**All Python Files — Churn Detail**")
            max_commits = max(
                (v["commit_count"] for v in churn["file_churn"].values()), default=1
            ) or 1
            for rel_path, data in sorted(
                churn["file_churn"].items(),
                key=lambda x: x[1]["commit_count"], reverse=True
            ):
                commits = data["commit_count"]
                st.write(f"`{rel_path}` — {commits} commits | "
                         f"last changed: {data['last_changed'] or 'never'}")
                st.progress(commits / max_commits)

        # ── Tab 5: AI Report ──────────────────────────────────────────────
        with tab5:
            st.subheader("🤖 AI-Generated Report")

            if report["error"]:
                st.error(f"Report generation failed: {report['error']}")
            else:
                st.markdown(report["report_text"])
                st.divider()

                # Download buttons
                col_dl1, col_dl2 = st.columns(2)
                with col_dl1:
                    st.download_button(
                        label="📄 Download Report (.md)",
                        data=report["report_text"],
                        file_name=f"{repo_name}_report.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                with col_dl2:
                    if os.path.exists(graph_path):
                        with open(graph_path, "rb") as gf:
                            st.download_button(
                                label="🔀 Download Graph (.html)",
                                data=gf,
                                file_name=f"{repo_name}_graph.html",
                                mime="text/html",
                                use_container_width=True
                            )

    finally:
        # Always clean up cloned repo from disk
        if repo_path:
            cleanup_repo(repo_path)

elif not run_btn:
    # Landing state
    st.info("👈 Enter a GitHub URL in the sidebar and click **Analyse Repo** to get started.")

    st.markdown("### Example repos to try")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.code("https://github.com/pallets/markupsafe")
        st.caption("Small, clean — good baseline")
    with col2:
        st.code("https://github.com/pallets/flask")
        st.caption("Medium — interesting graph")
    with col3:
        st.code("https://github.com/psf/requests")
        st.caption("Well-known — great hotspot demo")