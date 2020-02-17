import argparse
import json
from jinja2 import Environment, FileSystemLoader
from jinja2.utils import concat
import re
import os
import logging
import sys
import pathlib

# TODO: Move this script to its own repo to be distributed properly

# Debugging:
# $ export LOGLEVEL=DEBUG
# $ python manifest_utils.py render -t external-staging -e staging.gen3.biodatacatalyst.nhlbi.nih.gov -r 2020.02 2>&1 | head -n 4
# 2020-02-16 13:37:23,194 [DEBUG] tier: external-staging
# 2020-02-16 13:37:23,194 [DEBUG] env: staging.gen3.biodatacatalyst.nhlbi.nih.gov
# 2020-02-16 13:37:23,194 [DEBUG] release tag: 2020.02
# 2020-02-16 13:37:23,203 [DEBUG] Rendering result:

LOGLEVEL = os.environ.get('LOGLEVEL', 'WARNING').upper()
logging.basicConfig(
    level=LOGLEVEL, format="%(asctime)-15s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

def create_release_template(template_contents, new_versions_block):
  START_VERSIONS_BLOCK = '{% block versions %}'
  regex1 = re.compile(r'.*?%s' % (START_VERSIONS_BLOCK), re.S)
  before_versions_block = regex1.search(template_contents).group(0)
  END_VERSIONS_BLOCK = '{% endblock %}'
  regex2 = re.compile(r'%s.*' % (END_VERSIONS_BLOCK), re.S)
  after_versions_block = regex2.search(template_contents).group(0)

  new_release_template = before_versions_block + new_versions_block + '\n  ' + after_versions_block
  return new_release_template

def load_template(template_contents):
  return Environment(loader=FileSystemLoader('./')).from_string(template_contents)

def render_manifest(tier, environment, release = None):
  target_manifest_template = '{}/{}/manifest.json'.format(tier, environment)
  with open(target_manifest_template, 'r') as template_file:
    template_contents = template_file.read()
  template = load_template(template_contents)

  if release:
    log.debug('release tag: {}'.format(release))
    # Identify services declared in this manifiest
    versions_block = concat(template.blocks['versions'](template.new_context({})))
    new_versions_block = ""
    for version_row in versions_block.splitlines():
      # ignore empty lines
      if len(version_row) <= 4:
        continue
      new_version_row = version_row[0:version_row.rfind(':')+1] + release + version_row[version_row.rfind('"'):len(version_row)]
      # log.debug('version_replaced: {}'.format(new_version_row))
      new_versions_block = new_versions_block + '\n' + new_version_row
    new_versions_block = new_versions_block + '\n' + '    {{ super() }}'
    log.debug('new_versions_block: {}'.format(new_versions_block))

    # inject the release tag across all services versions
    release_template_contents = create_release_template(template_contents, new_versions_block)
    # override original template ref
    template = load_template(release_template_contents)

  log.debug('test')
  rendered_manifest = template.render(hostname=environment, tier=tier)
  log.debug('Rendering result:')
  log.debug(rendered_manifest)

  try:
    os.makedirs(environment, exist_ok=True)
    with open('{}/manifest.json'.format(environment), "w") as manifest_file:
      manifest_file.write(rendered_manifest)
    # TODO: Quick JSON validation
  except IOError as ioe:
    print('oops! Something went wrong: {}'.format(ioe))


def make_parser():
    parser = argparse.ArgumentParser(
            description="Rendering Gen3 Manifests",
            formatter_class=argparse.RawTextHelpFormatter,
            epilog="""\
This script renders gen3 manifests through Jinja-powered templating & inheritance to avoid redundant JSON blocks across different environments' manifests.
The general syntax for this script is:

manifest_utils <command>
e.g., manifest_utils render <tier> <environment>

The most commonly used commands are:
   render    Creates a folder named after the environment's name and a manifest.json file
             containing all the information inherited from its correspondent tier & base manifests
             e.g. $ manifest_utils render -t internal-staging -e preprod.gen3.biodatacatalyst.nhlbi.nih.gov 
""")

    subparsers = parser.add_subparsers()

    parser_render = subparsers.add_parser('render', description='Renders a manifest.json file')
    parser_render.add_argument(
        "-t",
        "--tier",
        dest="tier",
        required=True,
        type=str,
        help="name of the tier (internal-staging, external-staging or prod)"
    )
    parser_render.add_argument(
        "-e",
        "--env",
        dest="env",
        required=True,
        type=str,
        help="name of the environment (e.g., preprod.gen3.biodatacatalyst.nhlbi.nih.gov)"
    )
    parser_render.add_argument(
        "-r",
        "--release",
        dest="release",
        required=False,
        type=str,
        help="OPTIONAL: Gen3 Core Release tag following the <year>.<month> naming pattern (e.g., 2020.02). This optional argument applies the same version to all services."
    )

    parser.set_defaults(func=render)
    return parser


def main():
  parser = make_parser()
  args = parser.parse_args()
  if len(args._get_kwargs()) == 1:
    parser.print_help(sys.stderr)
    sys.exit(1)
  args.func(args)

def render(args):
    manifest_tier = args.tier
    manifest_env = args.env
    log.debug('tier: {}'.format(manifest_tier))
    log.debug('env: {}'.format(manifest_env))

    render_manifest(manifest_tier, manifest_env, args.release)

if __name__ == "__main__":
    main()
