from azure.devops.credentials import BasicAuthentication
from azure.devops.connection import Connection
import argparse
from base64 import b64encode
from enum import Enum
import os
import os.path
import shutil
from tempfile import mkdtemp,NamedTemporaryFile
import urllib.request
from zipfile import ZipFile

Organization_url = 'https://dev.azure.com/dnceng'
Repository_id = 'dotnet/coreclr'
Repository_type = 'GitHub'

def command_line_parser():
    description = """Downloads Azure DevOps build artifacts
    """

    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--build_arch', dest='build_arch', required=True, choices=['arm', 'arm64', 'x64', 'x86'])
    parser.add_argument('--build_os', dest='build_os', required=True, choices=['Windows_NT', 'Linux', 'Linux_musl', 'OSX'])
    parser.add_argument('--build_type', dest='build_type', required=True, default='Checked', choices=['Debug', 'Checked', 'Release'])

    parser.add_argument('--project_name', dest='project_name', default='public', choices=['public', 'internal'])
    parser.add_argument('--branch_name', dest='branch_name', default='refs/heads/master')
    parser.add_argument('--source_version', dest='source_version', required=True)
    parser.add_argument('--personal_access_token', dest='personal_access_token')

    parser.add_argument('--coreclr_directory', dest='coreclr_directory', required=True)

    return parser

def download_build_artifact(project_name, branch_name, source_version, personal_access_token, artifact_name, output_filename):

    credentials = BasicAuthentication('', personal_access_token)
    connection = Connection(base_url=Organization_url, creds=credentials)

    build_client = connection.clients.get_build_client()

    builds = build_client.get_builds(project=project_name, branch_name=branch_name, repository_id=Repository_id, repository_type=Repository_type)
    builds = [build for build in builds if build.source_version == source_version]

    if len(builds) == 0:
        raise RuntimeError('There is no build corresponding to source_version: {0}'.format(source_version))

    if len(builds) != 1:
        raise RuntimeError('There is more than one build corresponding to source_version: {0}'.format(source_version))

    build_id = builds[0].id

    artifact = build_client.get_artifact(project='public', build_id=build_id, artifact_name=artifact_name)
    artifact_download_url = artifact.resource.download_url

    base64_personal_access_token = b64encode(str.encode('{0}:{1}'.format('', personal_access_token))).decode()

    opener = urllib.request.build_opener()
    opener.addheaders = [('Authorization', 'Basic {0}'.format(base64_personal_access_token))]

    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(artifact_download_url, output_filename)

def product_directory_artifact_name(build_arch, build_os, build_type):
    return '{0}_{1}_{2}_build'.format(build_os, build_arch, build_type.lower())

def unpack_to_product_directory(artifact_zipfile_name, product_directory):
    if os.path.isdir(product_directory):
        raise RuntimeError('Directory \'{0}\' already exists'.format(product_directory))

    temporary_directory = mkdtemp()

    with ZipFile(artifact_zipfile_name) as zf:
        zf.extractall(temporary_directory)

    shutil.copytree(os.path.join(temporary_directory, os.listdir(temporary_directory)[0]), product_directory)
    shutil.rmtree(temporary_directory)

if __name__ == '__main__':
    args = command_line_parser().parse_args()

    build_arch = args.build_arch
    build_os = args.build_os
    build_type = args.build_type

    artifact_name = product_directory_artifact_name(build_arch, build_os, build_type)

    project_name = args.project_name
    branch_name = args.branch_name
    source_version = args.source_version
    personal_access_token = args.personal_access_token

    artifact_zipfile_name = os.path.join(os.getcwd(), 'bin-Product-{0}.{1}.{2}-{3}.zip'.format(build_os, build_arch, build_type, source_version))

    if not os.path.isfile(artifact_zipfile_name):
        download_build_artifact(project_name, branch_name, source_version, personal_access_token, artifact_name, artifact_zipfile_name)

    coreclr_directory = args.coreclr_directory
    product_directory = os.path.join(coreclr_directory, 'bin', 'Product', '{0}.{1}.{2}'.format(build_os, build_arch, build_type))

    unpack_to_product_directory(artifact_zipfile_name, product_directory)
