"""Pins on the Mac App Store upload planner and packaging.

The planner in runner/tools/apple_store.py carries the chain
from the frozen macOS binaries to an uploaded store package,
and the rules the lane learned standing it up: demand the
signing material in chain order and refuse on the first
missing piece, naming it and where it comes from; never plan
an upload the API key cannot sign; sign the bundle before
packaging it and package it before uploading it; render
the bundle's Info.plist from the packaging template so the
bundle ID the App Store Connect record was created with can
never drift from the build; map the release's 4 part version
into the shapes Apple's validation accepts, after the first
upload was refused for carrying the raw number; and carry
the listing's category and the bundle icon the same refusal
named as missing. These tests pin those rules so a
later edit cannot quietly thin them. The planner opens no
socket and runs no command; the store call itself is the
pipeline's, with the material it holds as CI secrets.
"""

import importlib.util
import os
import plistlib
import re
import struct
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "apple_store",
    os.path.join(REPO, "runner", "tools", "apple_store.py"))
apple_store = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(apple_store)


def _read(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def _full_state():
    return {
        "app_distribution_p12": True,
        "installer_distribution_p12": True,
        "provisioning_profile": True,
        "api_key": True,
        "api_key_id": "ABC123DEFG",
        "api_key_issuer_id": "12345678-1234-1234-1234-1234567890ab",
    }


class ConstantsTest(unittest.TestCase):

    def test_bundle_id_matches_the_store_record(self):
        self.assertEqual("ai.pigeon-home.homing-pigeon",
                         apple_store.BUNDLE_ID)

    def test_team_id_is_the_enrollment_team(self):
        self.assertEqual("3PH9A88USW", apple_store.TEAM_ID)

    def test_application_identifier_joins_team_and_bundle(self):
        self.assertEqual("3PH9A88USW.ai.pigeon-home.homing-pigeon",
                         apple_store.APPLICATION_IDENTIFIER)

    def test_sku_matches_the_store_record(self):
        self.assertEqual("HOMINGPIGEON-MAC-001", apple_store.SKU)

    def test_signing_identities_are_the_store_pair(self):
        self.assertEqual("Apple Distribution",
                         apple_store.APP_DISTRIBUTION_IDENTITY)
        self.assertEqual("Mac Installer Distribution",
                         apple_store.INSTALLER_DISTRIBUTION_IDENTITY)

    def test_category_is_the_listing_category(self):
        self.assertEqual("public.app-category.developer-tools",
                         apple_store.APP_CATEGORY_UTI)

    def test_icon_names_the_packaged_icns(self):
        self.assertEqual("AppIcon", apple_store.ICON_FILE_NAME)
        self.assertEqual("packaging/macos/AppIcon.icns",
                         apple_store.ICON_SOURCE)
        self.assertEqual("Contents/Resources/AppIcon.icns",
                         apple_store.ICON_BUNDLE_PATH)

    def test_pieces_are_demanded_in_chain_order(self):
        keys = [entry[0] for entry in apple_store.REQUIRED_PIECES]
        self.assertEqual(["app_distribution_p12",
                          "installer_distribution_p12",
                          "provisioning_profile",
                          "api_key"], keys)


class PlanUploadTest(unittest.TestCase):

    def test_full_state_plans_the_whole_chain(self):
        plan = apple_store.plan_upload(_full_state(), "3.17.33.1")
        self.assertTrue(plan["ok"])
        self.assertTrue(plan["commands"])

    def test_chain_orders_sign_package_upload(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        joined = "\n".join(commands)
        sign = joined.index("codesign --force")
        verify = joined.index("codesign --verify")
        package = joined.index("productbuild")
        check = joined.index("pkgutil --check-signature")
        upload = joined.index("altool --upload-app")
        self.assertLess(sign, verify)
        self.assertLess(verify, package)
        self.assertLess(package, check)
        self.assertLess(check, upload)

    def test_bundle_is_signed_with_the_app_identity(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        signing = [c for c in commands if c.startswith("codesign --force")]
        self.assertEqual(3, len(signing))
        for command in signing:
            self.assertIn('"Apple Distribution"', command)
            self.assertIn("packaging/macos/entitlements.plist", command)

    def test_package_is_signed_with_the_installer_identity(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        (package,) = [c for c in commands if c.startswith("productbuild")]
        self.assertIn("ai.pigeon-home.homing-pigeon", package)
        self.assertIn("3.17.33.1", package)
        # productbuild matches --sign against the keychain
        # common name, not the portal type name: the first
        # carried out run stopped on exactly that. The plan
        # must hand it the resolved keychain name, and must
        # never hand it the bare type name again.
        self.assertNotIn('"Mac Installer Distribution"', package)
        self.assertIn(apple_store.installer_identity_lookup(), package)

    def test_installer_identity_is_resolved_from_the_keychain(self):
        lookup = apple_store.installer_identity_lookup()
        self.assertTrue(lookup.startswith("$(security find-identity"))
        self.assertIn("3rd Party Mac Developer Installer:", lookup)
        self.assertIn("(3PH9A88USW)", lookup)
        self.assertIn("head -n 1", lookup)
        # No team display name is hardcoded anywhere in the
        # plan: the name comes from the keychain at run time.
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        for command in commands:
            self.assertNotIn("Installer: Andrew", command)

    def test_installer_keychain_prefix_is_the_imported_name(self):
        self.assertEqual("3rd Party Mac Developer Installer",
                         apple_store.INSTALLER_KEYCHAIN_IDENTITY_PREFIX)

    def test_identity_gate_stands_before_productbuild(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        gate = apple_store.installer_identity_gate()
        self.assertIn(gate, commands)
        self.assertIn("security find-identity", gate)
        self.assertIn("grep -q", gate)
        self.assertIn("3rd Party Mac Developer Installer:", gate)
        self.assertIn("(3PH9A88USW)", gate)
        package = next(c for c in commands
                       if c.startswith("productbuild"))
        self.assertLess(commands.index(gate), commands.index(package))

    def test_bundle_signing_still_uses_the_app_identity(self):
        # codesign accepted the Apple Distribution type name
        # and verified on the carried out run, so only the
        # indicted productbuild step changes shape.
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        signing = [c for c in commands if c.startswith("codesign --force")]
        self.assertEqual(3, len(signing))
        for command in signing:
            self.assertNotIn("find-identity", command)

    def test_upload_uses_the_api_key_facts(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        upload = commands[-1]
        self.assertIn("--apiKey ABC123DEFG", upload)
        self.assertIn("--apiIssuer 12345678-1234-1234-1234-"
                      "1234567890ab", upload)
        self.assertIn("--type macos", upload)

    def test_profile_is_embedded_before_signing(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        joined = "\n".join(commands)
        self.assertLess(joined.index("embedded.provisionprofile"),
                        joined.index("codesign --force"))

    def test_info_plist_is_rendered_by_the_tool(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        renders = [c for c in commands if "--render-info-plist" in c]
        self.assertEqual(1, len(renders))
        self.assertIn("--version 3.17.33.1", renders[0])

    def test_icon_is_copied_into_resources_before_signing(self):
        commands = apple_store.plan_upload(
            _full_state(), "3.17.33.1")["commands"]
        copies = [c for c in commands
                  if c.startswith("cp packaging/macos/AppIcon.icns")]
        self.assertEqual(1, len(copies))
        self.assertIn("Contents/Resources/AppIcon.icns", copies[0])
        joined = "\n".join(commands)
        self.assertLess(joined.index("Contents/Resources/AppIcon.icns"),
                        joined.index("codesign --force"))

    def test_missing_first_piece_refuses_and_names_it(self):
        plan = apple_store.plan_upload({}, "3.17.33.1")
        self.assertFalse(plan["ok"])
        self.assertEqual([], plan["commands"])
        self.assertIn("Apple Distribution", plan["reason"])

    def test_each_missing_piece_refuses_in_order(self):
        state = {}
        named = {"app_distribution_p12": "Apple Distribution",
                 "installer_distribution_p12":
                     "Mac Installer Distribution",
                 "provisioning_profile": "provisioning profile",
                 "api_key": "API key"}
        for key, _piece, _source in apple_store.REQUIRED_PIECES:
            plan = apple_store.plan_upload(state, "3.17.33.1")
            self.assertFalse(plan["ok"], key)
            self.assertIn(named[key], plan["reason"])
            state[key] = True
        state["api_key_id"] = "ABC123DEFG"
        state["api_key_issuer_id"] = "12345678-1234-1234-1234-1234567890ab"
        self.assertTrue(apple_store.plan_upload(state, "3.17.33.1")["ok"])

    def test_missing_profile_names_the_portal(self):
        state = _full_state()
        del state["provisioning_profile"]
        plan = apple_store.plan_upload(state, "3.17.33.1")
        self.assertFalse(plan["ok"])
        self.assertIn("provisioning profile", plan["reason"])
        self.assertIn("portal", plan["reason"])

    def test_api_key_without_ids_refuses(self):
        state = _full_state()
        del state["api_key_issuer_id"]
        plan = apple_store.plan_upload(state, "3.17.33.1")
        self.assertFalse(plan["ok"])
        self.assertIn("Issuer ID", plan["reason"])
        self.assertEqual([], plan["commands"])

    def test_no_command_runs_without_every_piece(self):
        for key, _piece, _source in apple_store.REQUIRED_PIECES:
            state = _full_state()
            del state[key]
            plan = apple_store.plan_upload(state, "3.17.33.1")
            self.assertEqual([], plan["commands"], key)


class InfoPlistTest(unittest.TestCase):

    def test_template_carries_tokens_not_numbers(self):
        text = _read(os.path.join("packaging", "macos", "Info.plist"))
        self.assertIn("__VERSION__", text)
        self.assertIn("__BUILD__", text)

    def test_rendered_plist_parses_and_matches_the_record(self):
        rendered = apple_store.render_info_plist("3.17.33.1")
        parsed = plistlib.loads(rendered.encode("utf-8"))
        self.assertEqual("ai.pigeon-home.homing-pigeon",
                         parsed["CFBundleIdentifier"])
        self.assertEqual("3.17.33",
                         parsed["CFBundleShortVersionString"])
        self.assertEqual("3017.33.1", parsed["CFBundleVersion"])
        self.assertEqual("homing-pigeon", parsed["CFBundleExecutable"])
        self.assertEqual("Homing Pigeon Runner", parsed["CFBundleName"])

    def test_rendered_plist_takes_an_explicit_build(self):
        rendered = apple_store.render_info_plist("3.17.33.1", build="42")
        parsed = plistlib.loads(rendered.encode("utf-8"))
        self.assertEqual("42", parsed["CFBundleVersion"])
        self.assertEqual("3.17.33",
                         parsed["CFBundleShortVersionString"])

    def test_rendered_plist_names_the_category(self):
        rendered = apple_store.render_info_plist("3.17.33.1")
        parsed = plistlib.loads(rendered.encode("utf-8"))
        self.assertEqual("public.app-category.developer-tools",
                         parsed["LSApplicationCategoryType"])

    def test_rendered_plist_names_the_icon(self):
        rendered = apple_store.render_info_plist("3.17.33.1")
        parsed = plistlib.loads(rendered.encode("utf-8"))
        self.assertEqual("AppIcon", parsed["CFBundleIconFile"])

    def test_template_names_the_category_and_the_icon(self):
        text = _read(os.path.join("packaging", "macos", "Info.plist"))
        self.assertIn("LSApplicationCategoryType", text)
        self.assertIn("public.app-category.developer-tools", text)
        self.assertIn("CFBundleIconFile", text)

    def test_rendered_plist_has_no_tokens_left(self):
        rendered = apple_store.render_info_plist("3.17.33.1")
        self.assertNotIn("__VERSION__", rendered)
        self.assertNotIn("__BUILD__", rendered)


class StoreVersionTest(unittest.TestCase):
    """The mapping Apple's validation imposed on the numbers.

    The first upload was refused because CFBundleVersion and
    CFBundleShortVersionString carried the release's raw 4
    part version; the store accepts at most three
    non-negative integers in each. The short version is the
    first three components and the build is the packed
    mapping (major and minor packed into the first integer,
    then the token millions and the counter), so the build
    advances with every component of the release odometer.
    The build mapping this one replaced carried only the
    last two components and went backwards at the 3.18
    transition; StoreBuildMonotonicTest below pins the
    packed mapping transition by transition.
    """

    def test_short_version_is_the_first_three_components(self):
        self.assertEqual("3.17.33",
                         apple_store.store_version("3.17.33.1"))

    def test_build_is_the_packed_mapping(self):
        self.assertEqual("3017.33.1",
                         apple_store.store_build("3.17.33.1"))

    def test_next_odometer_number_maps_forward(self):
        self.assertEqual("3.17.33",
                         apple_store.store_version("3.17.33.2"))
        self.assertEqual("3017.33.2",
                         apple_store.store_build("3.17.33.2"))

    def test_next_token_count_maps_forward(self):
        self.assertEqual("3.17.34",
                         apple_store.store_version("3.17.34.1"))
        self.assertEqual("3017.34.1",
                         apple_store.store_build("3.17.34.1"))

    def test_mapped_numbers_stay_inside_the_store_limit(self):
        for version in ("3.17.33.1", "3.17.33.2", "3.17.34.1",
                        "3.18.5.12", "4.0.100.9"):
            for mapped in (apple_store.store_version(version),
                           apple_store.store_build(version)):
                parts = mapped.split(".")
                self.assertLessEqual(len(parts), 3, (version, mapped))
                self.assertTrue(
                    all(part.isdigit() for part in parts),
                    (version, mapped))

    def test_build_increases_as_the_odometer_advances(self):
        def key(version):
            return tuple(int(part) for part in
                         apple_store.store_build(version).split("."))
        self.assertLess(key("3.17.33.1"), key("3.17.33.2"))
        self.assertLess(key("3.17.33.2"), key("3.17.34.1"))

    def test_rendered_plist_carries_the_mapped_numbers(self):
        for version, short, build in (
                ("3.17.33.1", "3.17.33", "3017.33.1"),
                ("3.17.33.2", "3.17.33", "3017.33.2"),
                ("3.17.34.1", "3.17.34", "3017.34.1")):
            parsed = plistlib.loads(
                apple_store.render_info_plist(version).encode("utf-8"))
            self.assertEqual(short,
                             parsed["CFBundleShortVersionString"])
            self.assertEqual(build, parsed["CFBundleVersion"])

    def test_rendered_plist_never_carries_the_raw_version(self):
        rendered = apple_store.render_info_plist("3.17.33.1")
        self.assertNotIn("3.17.33.1", rendered)

    def test_a_non_release_version_shape_is_refused(self):
        for bad in ("3.17.33", "3.17.33.1.5", "1.0", "three",
                    "3.17.33.x", ""):
            with self.assertRaises(ValueError, msg=bad):
                apple_store.store_version(bad)
            with self.assertRaises(ValueError, msg=bad):
                apple_store.store_build(bad)
            with self.assertRaises(ValueError, msg=bad):
                apple_store.render_info_plist(bad)


class StoreBuildMonotonicTest(unittest.TestCase):
    """The build number must rise at every version transition.

    An outside review (2026-11-23) checked the standing
    mapping by hand and found the next Mac build going
    backwards: the uploaded 3.17.33.3 carried build 33.3
    while 3.18.33.1 would carry 33.1, because the old build
    used only the third and fourth components. Apple
    requires build numbers to keep increasing, and a change
    to ANY of the four components is a new release, so the
    build must answer to all four. The packed mapping is
    (major * 1000 + minor, token millions, counter): three
    integers inside the store limit, compared componentwise,
    rising strictly with the release odometer. The probe and
    its supposition stand in
    docs/infrastructure-documents/project/
    apple-build-number-probe-2026-11-23.md.
    """

    def _key(self, version):
        return tuple(int(part) for part in
                     apple_store.store_build(version).split("."))

    def test_build_packs_all_four_components(self):
        self.assertEqual("3017.33.1",
                         apple_store.store_build("3.17.33.1"))

    def test_the_reviews_transition_maps_forward(self):
        # The exact pair the review named: the uploaded build
        # and the latest release that would have gone under it.
        self.assertEqual("3017.33.3",
                         apple_store.store_build("3.17.33.3"))
        self.assertEqual("3018.33.1",
                         apple_store.store_build("3.18.33.1"))
        self.assertLess(self._key("3.17.33.3"),
                        self._key("3.18.33.1"))

    def test_counter_change_alone_raises_the_build(self):
        self.assertLess(self._key("3.17.33.1"),
                        self._key("3.17.33.2"))

    def test_token_change_raises_the_build_past_a_counter_reset(self):
        # The counter restarts at 1 when the token millions
        # figure advances; the build must still rise.
        self.assertLess(self._key("3.17.33.9"),
                        self._key("3.17.34.1"))

    def test_minor_change_alone_raises_the_build(self):
        self.assertLess(self._key("3.17.33.1"),
                        self._key("3.18.33.1"))

    def test_major_change_alone_raises_the_build(self):
        self.assertLess(self._key("3.17.33.1"),
                        self._key("4.17.33.1"))

    def test_major_change_raises_the_build_past_a_full_reset(self):
        self.assertLess(self._key("3.99.99.9"),
                        self._key("4.0.0.1"))

    def test_every_component_moves_the_build_number(self):
        base = apple_store.store_build("3.17.33.1")
        for bumped in ("4.17.33.1", "3.18.33.1", "3.17.34.1",
                       "3.17.33.2"):
            self.assertNotEqual(base,
                                apple_store.store_build(bumped),
                                bumped)

    def test_builds_rise_strictly_in_odometer_order(self):
        ordered = ["3.17.33.1", "3.17.33.2", "3.17.33.9",
                   "3.17.34.1", "3.17.34.2", "3.18.33.1",
                   "3.18.34.1", "4.0.0.1", "4.17.33.1"]
        keys = [self._key(version) for version in ordered]
        for earlier, later in zip(keys, keys[1:]):
            self.assertLess(earlier, later)

    def test_build_order_matches_version_order_across_the_grid(self):
        versions = []
        for major in (3, 4):
            for minor in (0, 17, 18, 999):
                for tokens in (0, 33, 34):
                    for counter in (1, 2, 99):
                        versions.append("%d.%d.%d.%d"
                                        % (major, minor, tokens,
                                           counter))
        versions.sort(key=lambda v: tuple(
            int(part) for part in v.split(".")))
        keys = [self._key(version) for version in versions]
        for earlier, later in zip(keys, keys[1:]):
            self.assertLess(earlier, later)

    def test_packed_build_stays_inside_the_store_limit(self):
        for version in ("3.17.33.1", "3.18.33.1", "4.0.0.1",
                        "3.999.999.999"):
            parts = apple_store.store_build(version).split(".")
            self.assertEqual(3, len(parts), version)
            self.assertTrue(all(part.isdigit() for part in parts),
                            version)

    def test_packed_build_clears_the_old_mappings_history(self):
        # Every build the old mapping ever produced for the
        # standing lines began with a token figure in the low
        # thirties; the packed first component stands above
        # any of them, so the first packed build App Store
        # Connect sees is higher than the highest old build.
        self.assertGreater(self._key("3.17.33.1")[0], 99)

    def test_a_minor_at_the_packing_width_is_refused(self):
        # A minor of 1000 or more would pack into the major's
        # digits and could collide; the mapping refuses it
        # rather than guessing.
        with self.assertRaises(ValueError):
            apple_store.store_build("3.1000.33.1")

    def test_rendered_plist_carries_the_packed_build(self):
        parsed = plistlib.loads(
            apple_store.render_info_plist("3.18.33.1").encode("utf-8"))
        self.assertEqual("3.18.33",
                         parsed["CFBundleShortVersionString"])
        self.assertEqual("3018.33.1", parsed["CFBundleVersion"])


class PackagingTest(unittest.TestCase):

    def test_entitlements_declare_the_app_sandbox(self):
        text = _read(os.path.join("packaging", "macos",
                                  "entitlements.plist"))
        parsed = plistlib.loads(text.encode("utf-8"))
        self.assertIs(True,
                      parsed["com.apple.security.app-sandbox"])

    def test_entitlements_declare_outgoing_network_client(self):
        # The runner initiates its mailbox and HTTPS
        # connections; under the App Sandbox those are refused
        # without the outgoing network entitlement, so the
        # store entitlements must carry it.
        text = _read(os.path.join("packaging", "macos",
                                  "entitlements.plist"))
        parsed = plistlib.loads(text.encode("utf-8"))
        self.assertIs(True,
                      parsed["com.apple.security.network.client"])

    def test_entitlements_carry_the_application_identifier(self):
        # TestFlight warning 90886: the first upload lacked an
        # application identifier in its signature. The value
        # joins the team ID and the bundle ID, matching the
        # provisioning profile the bundle embeds.
        text = _read(os.path.join("packaging", "macos",
                                  "entitlements.plist"))
        parsed = plistlib.loads(text.encode("utf-8"))
        self.assertEqual("3PH9A88USW.ai.pigeon-home.homing-pigeon",
                         parsed["com.apple.application-identifier"])
        self.assertEqual(apple_store.APPLICATION_IDENTIFIER,
                         parsed["com.apple.application-identifier"])
        self.assertEqual(
            "%s.%s" % (apple_store.TEAM_ID, apple_store.BUNDLE_ID),
            parsed["com.apple.application-identifier"])

    def test_entitlements_match_the_planner_expectation_exactly(self):
        # Both directions: the file may neither lose an entry
        # the planner expects nor gain one it does not, because
        # each entitlement is a claim App Review reads.
        text = _read(os.path.join("packaging", "macos",
                                  "entitlements.plist"))
        parsed = plistlib.loads(text.encode("utf-8"))
        self.assertEqual(apple_store.EXPECTED_ENTITLEMENTS, parsed)
        self.assertEqual(parsed,
                         apple_store.load_entitlements())

    def test_entitlements_check_refuses_drift(self):
        good = dict(apple_store.EXPECTED_ENTITLEMENTS)
        apple_store.check_entitlements(good)
        drifted = []
        missing_network = dict(good)
        del missing_network["com.apple.security.network.client"]
        drifted.append(missing_network)
        missing_identifier = dict(good)
        del missing_identifier["com.apple.application-identifier"]
        drifted.append(missing_identifier)
        wrong_identifier = dict(good)
        wrong_identifier["com.apple.application-identifier"] = (
            "3PH9A88USW.com.example.other")
        drifted.append(wrong_identifier)
        extra = dict(good)
        extra["com.apple.security.network.server"] = True
        drifted.append(extra)
        no_sandbox = dict(good)
        del no_sandbox["com.apple.security.app-sandbox"]
        drifted.append(no_sandbox)
        for parsed in drifted:
            with self.assertRaises(ValueError, msg=repr(parsed)):
                apple_store.check_entitlements(parsed)

    def test_plan_refuses_when_the_entitlements_file_drifts(self):
        drifted = dict(apple_store.EXPECTED_ENTITLEMENTS)
        del drifted["com.apple.security.network.client"]
        original = apple_store.load_entitlements
        apple_store.load_entitlements = lambda: drifted
        try:
            plan = apple_store.plan_upload(_full_state(),
                                           "3.17.33.1")
        finally:
            apple_store.load_entitlements = original
        self.assertFalse(plan["ok"])
        self.assertEqual([], plan["commands"])
        self.assertIn("entitlements", plan["reason"])

    def test_bundle_layout_embeds_the_profile(self):
        layout = dict(apple_store.BUNDLE_LAYOUT)
        self.assertEqual("Contents/embedded.provisionprofile",
                         layout["store/Homing Pigeon Mac App Store"
                                ".provisionprofile"])

    def test_bundle_layout_places_both_frozen_binaries(self):
        layout = dict(apple_store.BUNDLE_LAYOUT)
        self.assertEqual("Contents/MacOS/homing-pigeon",
                         layout["dist/homing-pigeon"])
        self.assertEqual("Contents/MacOS/install",
                         layout["dist/install"])
        self.assertEqual("Contents/Info.plist",
                         layout["packaging/macos/Info.plist"])

    def test_bundle_layout_places_the_icon_in_resources(self):
        layout = dict(apple_store.BUNDLE_LAYOUT)
        self.assertEqual("Contents/Resources/AppIcon.icns",
                         layout["packaging/macos/AppIcon.icns"])

    def test_icns_carries_the_full_size_set(self):
        # Apple's validation refused the first upload for a
        # bundle with no icon in ICNS format containing a
        # 512pt x 512pt @2x image. The packaged icon must be
        # a real ICNS and must carry that image (the ic10
        # entry, a 1024x1024 PNG) beside the rest of the set.
        with open(os.path.join(REPO, "packaging", "macos",
                               "AppIcon.icns"), "rb") as fh:
            data = fh.read()
        self.assertEqual(b"icns", data[:4])
        (total,) = struct.unpack(">I", data[4:8])
        self.assertEqual(len(data), total)
        entries = {}
        offset = 8
        while offset < len(data):
            ostype = data[offset:offset + 4].decode("ascii")
            (length,) = struct.unpack(">I", data[offset + 4:
                                                 offset + 8])
            entries[ostype] = data[offset + 8:offset + length]
            offset += length
        expected = {"icp4": 16, "ic11": 32, "icp5": 32,
                    "ic12": 64, "icp6": 64, "ic07": 128,
                    "ic13": 256, "ic08": 256, "ic14": 512,
                    "ic09": 512, "ic10": 1024}
        self.assertEqual(set(expected), set(entries))
        for ostype, size in expected.items():
            png = entries[ostype]
            self.assertEqual(b"\x89PNG\r\n\x1a\n", png[:8], ostype)
            width, height = struct.unpack(">II", png[16:24])
            self.assertEqual((size, size), (width, height), ostype)


class WorkflowTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = _read(os.path.join(".github", "workflows",
                                      "macos-store.yml"))

    def test_workflow_runs_the_planner(self):
        self.assertIn("runner/tools/apple_store.py", self.text)

    def test_workflow_runs_on_a_mac(self):
        self.assertIn("runs-on: macos-15", self.text)

    def test_workflow_hangs_on_the_release(self):
        self.assertIn("release:", self.text)
        self.assertIn("workflow_dispatch:", self.text)

    def test_workflow_reads_the_material_from_secrets(self):
        for secret in ("APPLE_APP_DISTRIBUTION_P12",
                       "APPLE_INSTALLER_DISTRIBUTION_P12",
                       "APPLE_PROVISIONING_PROFILE",
                       "ASC_API_KEY_P8", "ASC_API_KEY_ID",
                       "ASC_API_ISSUER_ID", "APPLE_P12_PASSWORD"):
            self.assertIn("secrets." + secret, self.text)

    def test_workflow_imports_into_a_temporary_keychain(self):
        self.assertIn("security create-keychain", self.text)
        self.assertIn("security import store/app-distribution.p12",
                      self.text)
        self.assertIn("security import store/installer-distribution.p12",
                      self.text)

    def test_workflow_fails_loudly_when_the_planner_refuses(self):
        # A planner refusal (exit 3) means signing material is
        # missing and nothing was uploaded. The plan step must
        # end the run red with an error annotation and a summary
        # headed NOT uploaded; a green run that merely notes the
        # refusal reads as an upload in the run list (the outside
        # review of 2026-11-23).
        plan = self.text.split("- name: plan the upload", 1)[1]
        plan = plan.split("- name:", 1)[0]
        self.assertIn('if [ "$rc" -eq 3 ]; then', plan)
        self.assertIn("Mac App Store leg: NOT uploaded", plan)
        self.assertIn("::error title=macos-store::", plan)
        self.assertIn("exit 1", plan)
        self.assertNotIn("exit 0", plan)

    def test_build_workflow_dispatches_the_store_leg(self):
        # The release job publishes through
        # softprops/action-gh-release under the default
        # GITHUB_TOKEN, and GitHub starts no workflow run for an
        # event that token raises, workflow_dispatch excepted.
        # So the release event this workflow also listens for
        # never fires for a pipeline release, and the one upload
        # that stands followed a dispatch by hand. A job in
        # build.yml must dispatch this workflow by name once the
        # release job has succeeded, the pattern the proofs job
        # already follows for the same reason.
        build = _read(os.path.join(".github", "workflows",
                                   "build.yml"))
        match = re.search(r"(?ms)^  macos-store-dispatch:\n(.*?)(?=^  [a-z0-9_-]+:\n|\Z)",
                          build)
        self.assertIsNotNone(match, "build.yml has no macos-store-dispatch job")
        block = match.group(1)
        self.assertIn("startsWith(github.ref, 'refs/tags/v')", block)
        self.assertIn("needs.release.result == 'success'", block)
        self.assertIn("needs: [release]", block)
        self.assertIn("actions: write", block)
        self.assertIn('gh workflow run macos-store.yml', block)
        self.assertIn('-f version=', block)
        self.assertIn('VERSION: ${{ github.ref_name }}', block)


if __name__ == "__main__":
    unittest.main()
