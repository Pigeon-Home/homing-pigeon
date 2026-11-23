"""Plan the Mac App Store upload for one Homing Pigeon release.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

The App Store Connect record already stands (Homing Pigeon
Runner, macOS, bundle ID ai.pigeon-home.homing-pigeon, SKU
HOMINGPIGEON-MAC-001, created 2026-11-21 at the owner's
direction: submit anyway and let App Review decide). The
portal side also stands done: the Apple Distribution and Mac
Installer Distribution certificates were created from this
side's signing requests, the App ID was registered, and the
Mac App Store provisioning profile was generated, all on
2026-11-21. What was missing is the machine chain from the
frozen macOS binaries the build already produces to an
uploaded store package, and that chain is what this tool
plans.

The tool is a planner, not a publisher, in the same shape as
runner/tools/store_release.py beside it. Given the state of
the signing material (which pieces stand downloaded and
converted on the machine that will run the chain), it works
out the upload for one version:

- the pieces are demanded in chain order: the Apple
  Distribution .p12 (the certificate from the portal plus
  its private key, converted), the Mac Installer
  Distribution .p12, the provisioning profile downloaded
  from the portal, and the App Store Connect API key (the
  .p8 with its Key ID and Issuer ID) that the upload signs
  with. The first missing piece refuses the plan and names
  itself, because every later step depends on it and a
  half signed package helps nobody;
- once every piece stands present, the plan is the ordered
  command chain: assemble the .app bundle from the frozen
  binaries and the packaging template in packaging/macos,
  embed the profile, sign the bundle with the Apple
  Distribution identity under the App Sandbox entitlements,
  verify the signature, package the .pkg with productbuild
  signed by the Mac Installer Distribution identity, verify
  the package signature, and upload the package with altool
  under the API key.

One naming lesson the first carried out run taught
(2026-11-21): the portal type names above are not the names
the keychain holds. codesign accepts the Apple Distribution
type name and signed with it, so that step stands as it is.
productbuild does not: it stopped with "Could not find
appropriate signing identity for Mac Installer
Distribution", because the installer certificate's keychain
common name is the "3rd Party Mac Developer Installer:
<team name> (team ID)" form. The plan therefore resolves
the installer identity from the keychain at run time: a
find-identity gate first proves an identity carrying that
prefix for this team stands in the keychain, and the
productbuild step signs with the name that same lookup
returns, never a hardcoded team display name.

A second lesson came from the first upload itself
(2026-11-21): the chain signed and packaged cleanly, and
Apple's validation refused the archive with 4 errors. The
bundle's Info.plist carried no LSApplicationCategoryType;
its CFBundleVersion and CFBundleShortVersionString carried
the release's own 4 part version (3.17.33.1), where the
store accepts at most three non-negative integers in each;
and the bundle carried no icon. The fixes stand in the
template and in this tool: the template names the listing's
category and the bundle icon, the render maps the release
version into the shapes the store accepts (see
store_version and store_build), and the assembly copies
AppIcon.icns, built from assets/logo.png with the full size
set, into the bundle's Resources.

A third lesson came from an outside review of that upload
(2026-11-23). The entitlements the chain signed with
declared the App Sandbox and nothing else: no outgoing
network entitlement, though the runner initiates its
mailbox and HTTPS connections and the sandbox refuses
them without one; and no application identifier, which is
the gap Apple's own answer to the first upload had
already named as TestFlight warning 90886. Both entries
stand in the entitlements file now, the expected set
stands in this tool as EXPECTED_ENTITLEMENTS, and the
plan refuses when the file drifts from it in either
direction. The record of the probe stands in
docs/infrastructure-documents/project/macos-entitlements-probe-2026-11-23.md.

Nothing here opens a socket or runs a command. The pipeline
step that carries the plan out first imports the two .p12s
into a temporary keychain and places the profile at the
layout path the plan names, then runs the printed commands
on a macOS leg with the material held as CI secrets (see
docs/steady/design/auto-publish-design.md). Keeping the
decision pure is what lets the tests pin it.
"""

import argparse
import json
import os
import plistlib
import sys

BUNDLE_ID = "ai.pigeon-home.homing-pigeon"
TEAM_ID = "3PH9A88USW"
APP_NAME = "Homing Pigeon Runner"
APP_BUNDLE = APP_NAME.replace(" ", "") + ".app"
EXECUTABLE = "homing-pigeon"
INSTALLER_EXECUTABLE = "install"
SKU = "HOMINGPIGEON-MAC-001"

# The application identifier the provisioning profile was
# made for and the signed bundle must carry: the team ID
# joined to the bundle ID. The first upload (3.17.33.3,
# 2026-11-22) came back with TestFlight warning 90886
# because the signature carried no application identifier,
# and that build stands unavailable for TestFlight.
APPLICATION_IDENTIFIER = "%s.%s" % (TEAM_ID, BUNDLE_ID)

# The entitlements the signing chain hands to codesign, in
# the parsed form of packaging/macos/entitlements.plist.
# The App Sandbox is the store's requirement; the outgoing
# network client entitlement answers the runner's own shape
# (it initiates its mailbox and HTTPS connections, which
# the sandbox refuses without it); the application
# identifier matches the embedded profile. plan_upload
# refuses to plan when the file on disk drifts from this
# value in either direction, because each entitlement is a
# claim App Review reads and none may join or leave
# quietly.
EXPECTED_ENTITLEMENTS = {
    "com.apple.security.app-sandbox": True,
    "com.apple.security.network.client": True,
    "com.apple.application-identifier": APPLICATION_IDENTIFIER,
}

ENTITLEMENTS_SOURCE = "packaging/macos/entitlements.plist"

APP_DISTRIBUTION_IDENTITY = "Apple Distribution"
INSTALLER_DISTRIBUTION_IDENTITY = "Mac Installer Distribution"

# The listing's primary category, in the UTI form the
# bundle's LSApplicationCategoryType key carries. Apple's
# validation refuses a bundle that names no category; the
# category is the one the listing itself declares
# (Developer Tools), so the bundle and the listing agree.
APP_CATEGORY_UTI = "public.app-category.developer-tools"

# The bundle icon: CFBundleIconFile names it without the
# extension, the file stands in packaging/macos beside the
# Info.plist template, and the assembly copies it into the
# bundle's Resources. It is built from assets/logo.png
# (1600x1600, downscaled only) with the full size set, the
# 512pt @2x image (1024x1024) included, because Apple's
# validation refuses a bundle with no such icon.
ICON_FILE_NAME = "AppIcon"
ICON_SOURCE = "packaging/macos/AppIcon.icns"
ICON_BUNDLE_PATH = "Contents/Resources/AppIcon.icns"


def _release_parts(version):
    """Split a release version into its 4 integer parts.

    The release version is the 4 part number pyproject.toml
    carries (for example 3.17.33.1). Anything else is not a
    release version this tool can map for the store, and
    raises ValueError rather than guessing a shape.
    """
    if not isinstance(version, str):
        raise ValueError("release version %r is not the 4 part "
                         "number the store mapping expects"
                         % (version,))
    parts = version.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        raise ValueError("release version %r is not the 4 part "
                         "number the store mapping expects"
                         % version)
    return [int(part) for part in parts]


def store_version(version):
    """Return the store short version for a release version.

    Apple's validation accepts at most three non-negative
    integers in CFBundleShortVersionString, so the short
    version is the release version's first three components:
    3.17.33.1 ships as 3.17.33.
    """
    parts = _release_parts(version)
    return ".".join(str(part) for part in parts[:3])


def store_build(version):
    """Return the store build number for a release version.

    CFBundleVersion carries the release version's third and
    fourth components (33.1 for 3.17.33.1): two integers,
    inside the store's three integer limit, and increasing
    as the release odometer advances, within one short
    version (33.1, 33.2) and across the next (34.1).
    """
    parts = _release_parts(version)
    return "%d.%d" % (parts[2], parts[3])

# The installer certificate's keychain common name is not
# its portal type name above: an imported Mac Installer
# Distribution certificate stands in the keychain as
# "3rd Party Mac Developer Installer: <team name> (3PH9A88USW)".
# productbuild matches --sign against that common name, so
# the plan resolves the name from the keychain at run time
# (see installer_identity_lookup) instead of handing
# productbuild the type name, which it cannot find.
INSTALLER_KEYCHAIN_IDENTITY_PREFIX = "3rd Party Mac Developer Installer"


def installer_identity_lookup():
    """Return the shell substitution that resolves the
    installer signing identity from the keychain.

    The substitution runs security find-identity on the
    machine carrying the plan out, keeps the identity whose
    common name carries INSTALLER_KEYCHAIN_IDENTITY_PREFIX
    for this team, and yields that full common name. It is
    embedded in the productbuild command, so the name
    productbuild signs with is the name the keychain
    actually holds at run time, whatever the team's display
    name is.
    """
    return ("$(security find-identity -v | grep -o "
            "'%s: [^\"]* (%s)' | head -n 1)"
            % (INSTALLER_KEYCHAIN_IDENTITY_PREFIX, TEAM_ID))


def installer_identity_gate():
    """Return the plan step that proves the installer
    identity stands in the keychain before packaging.

    The step fails the chain where the identity is absent,
    in plain sight, instead of leaving productbuild to stop
    later with its own cannot-find line.
    """
    return ("security find-identity -v | grep -q "
            "'%s:.*(%s)'"
            % (INSTALLER_KEYCHAIN_IDENTITY_PREFIX, TEAM_ID))

# The signing material the chain needs, in the order the
# chain reaches for it. Each entry: the state key, the piece
# in plain words, and where the piece comes from. The plan
# refuses on the first missing piece and names it with its
# source, so the report that carries the refusal says exactly
# what to fetch next.
REQUIRED_PIECES = (
    ("app_distribution_p12",
     "the Apple Distribution .p12 (the certificate downloaded "
     "from the portal, converted with the private key that "
     "matches the signing request)",
     "Certificates in the Apple Developer portal; the "
     "certificate was created there on 2026-11-21"),
    ("installer_distribution_p12",
     "the Mac Installer Distribution .p12 (the certificate "
     "downloaded from the portal, converted with the private "
     "key that matches the signing request)",
     "Certificates in the Apple Developer portal; the "
     "certificate was created there on 2026-11-21"),
    ("provisioning_profile",
     "the Mac App Store provisioning profile downloaded "
     "from the portal (.provisionprofile)",
     "Profiles in the Apple Developer portal; the profile "
     "Homing Pigeon Mac App Store was created there on "
     "2026-11-21"),
    ("api_key",
     "the App Store Connect API key (.p8, with its Key ID "
     "and Issuer ID) that the upload signs with",
     "App Store Connect, Users and Access, Integrations; "
     "the account holder creates the key and it downloads "
     "exactly once"),
)

# The bundle layout the assembly step produces, as
# (source, path inside the .app) pairs. The frozen binaries
# come from the macOS build legs; the plist and the profile
# land at the places the store's own checks look for them.
BUNDLE_LAYOUT = (
    ("dist/homing-pigeon", "Contents/MacOS/homing-pigeon"),
    ("dist/install", "Contents/MacOS/install"),
    ("packaging/macos/Info.plist", "Contents/Info.plist"),
    (ICON_SOURCE, ICON_BUNDLE_PATH),
    ("store/Homing Pigeon Mac App Store.provisionprofile",
     "Contents/embedded.provisionprofile"),
)


def info_plist_template_path():
    """The on-disk Info.plist template the build renders.

    The template lives in packaging/macos beside the
    entitlements; it is the single source of the bundle's
    plist shape, and this tool only fills its numbers in.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "packaging", "macos",
                        "Info.plist")


def entitlements_path():
    """The on-disk entitlements file the signing chain uses.

    The file lives in packaging/macos beside the Info.plist
    template; every codesign step in the plan names it, so
    it is the single source of the bundle's entitlements.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "packaging", "macos",
                        "entitlements.plist")


def load_entitlements(text=None):
    """Return the parsed entitlements the chain will sign with.

    The text must parse as a plist whose top level is a
    dictionary; anything else raises ValueError, because a
    file codesign would read differently than the planner
    checked must never reach the signing step unnoticed.
    """
    if text is None:
        with open(entitlements_path(), encoding="utf-8") as fh:
            text = fh.read()
    try:
        parsed = plistlib.loads(text.encode("utf-8"))
    except Exception as exc:
        raise ValueError("the store entitlements at %s do not "
                         "parse as a plist: %s"
                         % (ENTITLEMENTS_SOURCE, exc))
    if not isinstance(parsed, dict):
        raise ValueError("the store entitlements at %s do not "
                         "parse to a dictionary: %r"
                         % (ENTITLEMENTS_SOURCE, parsed))
    return parsed


def check_entitlements(parsed):
    """Refuse entitlements that drift from the expected set.

    parsed: a mapping as load_entitlements returns. Any
    difference from EXPECTED_ENTITLEMENTS, a missing entry,
    a changed value or an added entry, raises ValueError
    naming the drift, so the file can neither lose the
    outgoing network entitlement or the application
    identifier silently nor gain a claim nobody reviewed.
    """
    if parsed != EXPECTED_ENTITLEMENTS:
        raise ValueError(
            "the store entitlements at %s carry %r, not the "
            "expected %r" % (ENTITLEMENTS_SOURCE, parsed,
                             EXPECTED_ENTITLEMENTS))


def render_info_plist(version, build=None, template_text=None):
    """Return the bundle's Info.plist text for one version.

    The template in packaging/macos carries __VERSION__ and
    __BUILD__ tokens where the numbers go. The version is
    the release's own version (the number pyproject.toml
    carries, the same number the GitHub release and the
    tarballs carry), mapped into the shapes the store
    accepts: the short version is store_version(version)
    and the build defaults to store_build(version), because
    Apple's validation refuses either key in the release's
    raw 4 part shape. The rendered text must parse as a
    plist and carry the bundle ID the App Store Connect
    record was created with, the mapped numbers, the
    listing's category and the bundle icon's name; anything
    else raises ValueError.
    """
    if template_text is None:
        with open(info_plist_template_path(), encoding="utf-8") as fh:
            template_text = fh.read()
    short = store_version(version)
    rendered = template_text.replace("__VERSION__", short)
    rendered = rendered.replace("__BUILD__", build or store_build(version))
    parsed = plistlib.loads(rendered.encode("utf-8"))
    if parsed.get("CFBundleIdentifier") != BUNDLE_ID:
        raise ValueError("rendered Info.plist carries the wrong "
                         "bundle ID: %r" % parsed.get(
                             "CFBundleIdentifier"))
    if parsed.get("CFBundleShortVersionString") != short:
        raise ValueError("rendered Info.plist carries the wrong "
                         "version: %r" % parsed.get(
                             "CFBundleShortVersionString"))
    if parsed.get("CFBundleVersion") != (build or store_build(version)):
        raise ValueError("rendered Info.plist carries the wrong "
                         "build: %r" % parsed.get("CFBundleVersion"))
    if parsed.get("LSApplicationCategoryType") != APP_CATEGORY_UTI:
        raise ValueError("rendered Info.plist carries the wrong "
                         "category: %r" % parsed.get(
                             "LSApplicationCategoryType"))
    if parsed.get("CFBundleIconFile") != ICON_FILE_NAME:
        raise ValueError("rendered Info.plist carries the wrong "
                         "icon name: %r" % parsed.get(
                             "CFBundleIconFile"))
    return rendered


def missing_pieces(state):
    """Return the required pieces absent from the state.

    state: a mapping from the REQUIRED_PIECES keys to truthy
    values for the pieces that stand present on the machine
    that will run the chain. The result keeps chain order.
    """
    return [entry for entry in REQUIRED_PIECES if not state.get(entry[0])]


def plan_upload(state, version):
    """Return the upload plan for one version.

    state: as in missing_pieces, plus the API key's facts
    under api_key_id and api_key_issuer_id when api_key
    stands present.

    The plan is a mapping: {"ok": bool, "reason": str,
    "commands": [str, ...]}. ok is False with an empty
    command list whenever the upload must not be attempted
    yet; the reason names the first missing piece and where
    it comes from.
    """
    missing = missing_pieces(state)
    if missing:
        key, piece, source = missing[0]
        return {
            "ok": False,
            "reason": "missing %s; it comes from %s" % (piece, source),
            "commands": [],
        }
    if not state.get("api_key_id") or not state.get("api_key_issuer_id"):
        return {
            "ok": False,
            "reason": "the App Store Connect API key stands present "
                      "but its Key ID or Issuer ID is missing; the "
                      "upload cannot sign without both",
            "commands": [],
        }
    try:
        check_entitlements(load_entitlements())
    except (OSError, ValueError) as exc:
        return {
            "ok": False,
            "reason": str(exc),
            "commands": [],
        }
    app = "store/" + APP_BUNDLE
    pkg = "store/HomingPigeonRunner-%s.pkg" % version
    commands = [
        # Assemble the bundle from the frozen binaries and
        # the packaging template, then embed the profile.
        "mkdir -p %s/Contents/MacOS" % app,
        "cp dist/homing-pigeon %s/Contents/MacOS/homing-pigeon" % app,
        "cp dist/install %s/Contents/MacOS/install" % app,
        "python3 runner/tools/apple_store.py --render-info-plist "
        "--version %s --out %s/Contents/Info.plist" % (version, app),
        "mkdir -p %s/Contents/Resources" % app,
        "cp %s %s/%s" % (ICON_SOURCE, app, ICON_BUNDLE_PATH),
        "cp \"store/Homing Pigeon Mac App Store.provisionprofile\" "
        "%s/Contents/embedded.provisionprofile" % app,
        # Sign everything in the bundle, innermost first in
        # practice; the two executables and then the bundle
        # itself, under the store entitlements.
        "codesign --force --sign \"%s\" --entitlements "
        "packaging/macos/entitlements.plist --options runtime "
        "%s/Contents/MacOS/install" % (APP_DISTRIBUTION_IDENTITY, app),
        "codesign --force --sign \"%s\" --entitlements "
        "packaging/macos/entitlements.plist --options runtime "
        "%s/Contents/MacOS/homing-pigeon" % (APP_DISTRIBUTION_IDENTITY,
                                             app),
        "codesign --force --sign \"%s\" --entitlements "
        "packaging/macos/entitlements.plist --options runtime "
        "%s" % (APP_DISTRIBUTION_IDENTITY, app),
        "codesign --verify --deep --strict --verbose=2 %s" % app,
        # Package and sign the installer, verify it, and
        # upload it under the API key. The gate proves the
        # installer identity stands in the keychain under
        # its keychain common name, and productbuild signs
        # with the name the lookup resolves there, not the
        # portal type name it cannot find.
        installer_identity_gate(),
        "productbuild --component %s /Applications --sign \"%s\" "
        "--identifier %s --version %s %s"
        % (app, installer_identity_lookup(), BUNDLE_ID,
           version, pkg),
        "pkgutil --check-signature %s" % pkg,
        "xcrun altool --upload-app --type macos --file %s "
        "--apiKey %s --apiIssuer %s"
        % (pkg, state["api_key_id"], state["api_key_issuer_id"]),
    ]
    return {
        "ok": True,
        "reason": "assemble, sign, package and upload version %s "
                  "for %s" % (version, BUNDLE_ID),
        "commands": commands,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Plan the Mac App Store upload for one version.")
    parser.add_argument("--state",
                        help="path to a JSON file holding the signing "
                             "material state: one key per required "
                             "piece, truthy when the piece stands "
                             "present, plus api_key_id and "
                             "api_key_issuer_id")
    parser.add_argument("--version",
                        help="the version to upload, e.g. 3.17.33.1")
    parser.add_argument("--render-info-plist", action="store_true",
                        help="render the bundle Info.plist for "
                             "--version instead of planning")
    parser.add_argument("--build",
                        help="build number for the rendered plist; "
                             "defaults to the version's mapped "
                             "store build (see store_build)")
    parser.add_argument("--out",
                        help="write the rendered plist here instead "
                             "of stdout")
    args = parser.parse_args(argv)
    if args.render_info_plist:
        if not args.version:
            parser.error("--render-info-plist needs --version")
        rendered = render_info_plist(args.version, args.build)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(rendered)
        else:
            print(rendered, end="")
        return 0
    if not args.state or not args.version:
        parser.error("planning needs --state and --version")
    with open(args.state, encoding="utf-8") as fh:
        state = json.load(fh)
    plan = plan_upload(state, args.version)
    print(plan["reason"])
    for command in plan["commands"]:
        print(command)
    return 0 if plan["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
