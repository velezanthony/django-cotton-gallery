"""Tests for the component dependency graph."""

from django_cotton_gallery.core.component_graph import (
    ComponentGraph,
    build_graph,
    extract_component_uses,
    scan_external_users,
)


class TestExtractUses:
    def test_no_components_referenced(self):
        assert extract_component_uses("<div>nothing</div>") == set()

    def test_finds_simple_reference(self):
        assert extract_component_uses("<c-atoms.button />") == {"atoms.button"}

    def test_skips_c_vars(self):
        # `<c-vars>` is the prop declaration meta-tag, not a component
        # reference — should never appear in the dependency graph.
        assert extract_component_uses('<c-vars title="x" />') == set()

    def test_finds_multiple_unique_refs(self):
        source = (
            "<c-atoms.button />"
            "<c-atoms.button>nested</c-atoms.button>"  # same — dedupes
            "<c-molecules.card />"
        )
        assert extract_component_uses(source) == {"atoms.button", "molecules.card"}

    def test_finds_dotted_paths(self):
        source = "<c-molecules.forms.input-group />"
        assert extract_component_uses(source) == {"molecules.forms.input-group"}


class TestBuildGraph:
    def test_empty_input(self):
        g = build_graph([])
        assert g.uses == {}
        assert g.used_by == {}

    def test_simple_one_uses_other(self):
        items = [
            ("molecules/card", "<c-atoms.button />"),
            ("atoms/button", "<button>x</button>"),
        ]
        g = build_graph(items)
        assert g.uses["molecules/card"] == frozenset({"atoms/button"})
        assert g.used_by["atoms/button"] == frozenset({"molecules/card"})

    def test_self_reference_is_dropped(self):
        items = [("atoms/button", "<c-atoms.button />")]
        g = build_graph(items)
        assert g.uses == {}
        assert g.used_by == {}

    def test_unknown_tag_is_dropped(self):
        # Reference to a component that isn't in the catalog (typo, deleted)
        # must not pollute the graph with non-existent paths.
        items = [("molecules/card", "<c-atoms.ghost />")]
        g = build_graph(items)
        assert g.uses == {}
        assert g.used_by == {}

    def test_multiple_users_of_one_component(self):
        items = [
            ("molecules/card", "<c-atoms.button />"),
            ("molecules/dialog", "<c-atoms.button />"),
            ("atoms/button", "<button>x</button>"),
        ]
        g = build_graph(items)
        assert g.used_by["atoms/button"] == frozenset({"molecules/card", "molecules/dialog"})

    def test_for_component_returns_sorted_lists(self):
        items = [
            ("molecules/card", "<c-atoms.zebra /><c-atoms.alpha />"),
            ("atoms/zebra", ""),
            ("atoms/alpha", ""),
        ]
        g = build_graph(items)
        uses, used_by = g.for_component("molecules/card")
        assert uses == ("atoms/alpha", "atoms/zebra")
        assert used_by == ()

    def test_dotted_subfolder_paths(self):
        # Tag `forms.input-group` should map to path `forms/input-group`.
        items = [
            ("molecules/card", "<c-forms.input-group />"),
            ("forms/input-group", ""),
        ]
        g = build_graph(items)
        assert g.uses["molecules/card"] == frozenset({"forms/input-group"})


class TestScanExternalUsers:
    def test_finds_consumer_template_referencing_component(self, tmp_path):
        # Layout: tmp_path/templates/cotton/atoms/button.html (catalog)
        #         tmp_path/templates/dashboard.html (consumer — uses the atom)
        cotton = tmp_path / "templates" / "cotton"
        cotton.mkdir(parents=True)
        (cotton / "atoms").mkdir()
        (cotton / "atoms" / "button.html").write_text("<button>{{ slot }}</button>")
        consumer = tmp_path / "templates" / "dashboard.html"
        consumer.write_text("<c-atoms.button>Click</c-atoms.button>")

        out = scan_external_users(
            catalog_paths=["atoms/button"],
            scan_roots=[tmp_path / "templates"],
            exclude_root=cotton,
        )
        assert out == {"atoms/button": ("dashboard.html",)}

    def test_skips_files_inside_the_catalog(self, tmp_path):
        # A reference INSIDE the catalog must be excluded — those are
        # already covered by the in-catalog `used_by` map.
        cotton = tmp_path / "templates" / "cotton"
        cotton.mkdir(parents=True)
        (cotton / "atoms").mkdir()
        (cotton / "atoms" / "button.html").write_text("<button>x</button>")
        (cotton / "molecules").mkdir()
        # Inside the catalog — should be ignored by the external scan.
        (cotton / "molecules" / "card.html").write_text("<c-atoms.button />")

        out = scan_external_users(
            catalog_paths=["atoms/button", "molecules/card"],
            scan_roots=[tmp_path / "templates"],
            exclude_root=cotton,
        )
        assert out == {}

    def test_unknown_tags_dropped(self, tmp_path):
        # References to components that don't exist in the catalog must
        # not pollute the result.
        cotton = tmp_path / "templates" / "cotton"
        cotton.mkdir(parents=True)
        consumer = tmp_path / "templates" / "page.html"
        consumer.write_text("<c-atoms.ghost />")

        out = scan_external_users(
            catalog_paths=["atoms/button"],  # ghost not listed
            scan_roots=[tmp_path / "templates"],
            exclude_root=cotton,
        )
        assert out == {}

    def test_multiple_consumers_for_same_component(self, tmp_path):
        cotton = tmp_path / "templates" / "cotton"
        cotton.mkdir(parents=True)
        a = tmp_path / "templates" / "a.html"
        b = tmp_path / "templates" / "b.html"
        a.write_text("<c-atoms.button />")
        b.write_text("<c-atoms.button />")

        out = scan_external_users(
            catalog_paths=["atoms/button"],
            scan_roots=[tmp_path / "templates"],
            exclude_root=cotton,
        )
        assert out["atoms/button"] == ("a.html", "b.html")

    def test_missing_scan_root_does_not_crash(self, tmp_path):
        # Defensive: a TEMPLATES DIRS entry that doesn't exist on disk
        # must be skipped without raising.
        out = scan_external_users(
            catalog_paths=["atoms/button"],
            scan_roots=[tmp_path / "no-such-dir"],
            exclude_root=tmp_path / "no-cotton",
        )
        assert out == {}


class TestTransitiveTrees:
    """`transitive_uses` and `transitive_used_by` walk the graph recursively
    to produce an impact tree. Cycles must be broken cleanly and depth
    must be capped to keep the rendered HTML bounded."""

    def _graph(self, edges: dict[str, list[str]]) -> ComponentGraph:
        # Build a graph from a forward-edges dict so the test cases stay
        # readable. Source synthesised on the fly with the right `<c-X.Y>` tags.
        items = []
        for path, uses in edges.items():
            tags = "".join(f"<c-{u.replace('/', '.')} />" for u in uses)
            items.append((path, tags))
        # Make sure even leaves with no outgoing edges still appear in the
        # catalog so `tag_to_path` resolves them.
        all_paths = set(edges.keys())
        for uses in edges.values():
            all_paths.update(uses)
        for path in all_paths:
            if path not in edges:
                items.append((path, ""))
        return build_graph(items)

    def test_uses_tree_simple_chain(self):
        # a → b → c (linear)
        g = self._graph({"a": ["b"], "b": ["c"], "c": []})
        tree = g.transitive_uses("a")
        assert tree.path == "a"
        assert len(tree.children) == 1
        assert tree.children[0].path == "b"
        assert tree.children[0].children[0].path == "c"

    def test_used_by_tree_inverse(self):
        # c is used by b which is used by a → tree from c shows a above b.
        g = self._graph({"a": ["b"], "b": ["c"]})
        tree = g.transitive_used_by("c")
        assert tree.path == "c"
        assert tree.children[0].path == "b"
        assert tree.children[0].children[0].path == "a"

    def test_cycle_detection_marks_node(self):
        # a → b → a (cycle). The 2nd `a` must be marked, not recursed.
        g = self._graph({"a": ["b"], "b": ["a"]})
        tree = g.transitive_uses("a")
        cycle_node = tree.children[0].children[0]
        assert cycle_node.path == "a"
        assert cycle_node.is_cycle is True
        assert cycle_node.children == ()

    def test_depth_limit_honored(self):
        # Linear chain longer than max_depth → tail truncated.
        g = self._graph({"a": ["b"], "b": ["c"], "c": ["d"], "d": []})
        tree = g.transitive_uses("a", max_depth=2)
        assert tree.path == "a"
        assert tree.children[0].path == "b"
        assert tree.children[0].children[0].path == "c"
        # `c` is at depth 2 (root=0, b=1, c=2) — at the limit, so its branch
        # truncates BEFORE recursing into `d`.
        assert tree.children[0].children[0].truncated is True
        assert tree.children[0].children[0].children == ()

    def test_leaf_with_no_dependencies(self):
        g = self._graph({"a": []})
        tree = g.transitive_uses("a")
        assert tree.path == "a"
        assert tree.children == ()
        assert tree.is_cycle is False
        assert tree.truncated is False
