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

APP_DISTRIBUTION_IDENTITY = "Apple Distribution"
INSTALLER_DISTRIBUTION_IDENTITY = "Mac Installer Distribution"

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


def render_info_plist(version, build=None, template_text=None):
    """Return the bundle's Info.plist text for one version.

    The template in packaging/macos carries __VERSION__ and
    __BUILD__ tokens where the numbers go; the version is
    the release's own version (the number pyproject.toml
    carries, the same number the GitHub release and the
    tarballs carry), and the build defaults to it. The
    rendered text must parse as a plist and carry the
    bundle ID the App Store Connect record was created
    with; anything else raises ValueError.
    """
    if template_text is None:
        with open(info_plist_template_path(), encoding="utf-8") as fh:
            template_text = fh.read()
    rendered = template_text.replace("__VERSION__", version)
    rendered = rendered.replace("__BUILD__", build or version)
    parsed = plistlib.loads(rendered.encode("utf-8"))
    if parsed.get("CFBundleIdentifier") != BUNDLE_ID:
        raise ValueError("rendered Info.plist carries the wrong "
                         "bundle ID: %r" % parsed.get(
                             "CFBundleIdentifier"))
    if parsed.get("CFBundleShortVersionString") != version:
        raise ValueError("rendered Info.plist carries the wrong "
                         "version: %r" % parsed.get(
                             "CFBundleShortVersionString"))
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
        # upload it under the API key.
        "productbuild --component %s /Applications --sign \"%s\" "
        "--identifier %s --version %s %s"
        % (app, INSTALLER_DISTRIBUTION_IDENTITY, BUNDLE_ID,
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
                             "defaults to the version")
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
