# Copyright 2024 Camptocamp SA (http://www.camptocamp.com)
# Copyright 2024 Dixmit
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import json

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


def _get_storage_vals(code, record):
    protocol = "odoofs"
    options = record
    #TODO: Remove after testing is completed
    name = record["name"]
    _logger.info(f"Moving code {code}: {name}, {protocol}, {options}, {record}")
    server_env_defaults = json.loads(record.get("server_env_defaults", {}))
    backend_type = json.loads(record.get("server_env_defaults", {})).get("backend_type_env_default", False) or options.get("backend_type", False)
    if backend_type == "filesystem":
        protocol = "file"
        options = {}

    if backend_type == "ftp":
        protocol = "ftp"
        options = {
            "host": server_env_defaults["ftp_server_env_default"],
            "port": server_env_defaults["ftp_port_env_default"],
            "username": server_env_defaults["ftp_login_env_default"],
            "password": server_env_defaults["ftp_password_env_default"],
        }
    if backend_type == "sftp":
        protocol = "sftp"
        options = {
            "host": server_env_defaults["sftp_host"],
            "ssh_kwargs": {
                "port": server_env_defaults["sftp_port"],
            },
        }
        if server_env_defaults["sftp_auth_method"] == "pwd":
            options["ssh_kwargs"].update(
                {
                    "username": server_env_defaults["sftp_user"],
                    "password": server_env_defaults["sftp_password"],
                }
            )
        elif server_env_defaults["sftp_auth_method"] == "ssh_key":
            _logger.warning(
                "SSH Key requires a PrivateKey file, but we are "
                "providing a string. Please check the migration."
            )
            options["ssh_kwargs"].update(
                {
                    "pkey": record["sftp_private_key"],
                }
            )
    if backend_type == "s3":
        protocol = "s3"
        options = {
            "endpoint_url": server_env_defaults["aws_host"],
            "key": server_env_defaults["aws_access_key_id"],
            "secret": server_env_defaults["aws_secret_access_key"],
        }
    #TODO: Remove after testing is completed
    name = record["name"]
    _logger.info(f"Moving code {code}: {name}, {protocol}, {options}, {record}")
    return {
        "name": record["name"],
        "code": code,
        "protocol": protocol,
        "options": json.dumps(options),
    }


@openupgrade.migrate()
def migrate(env, version):
    # make sure all backend_type can be mapped even if corresponding modules
    # have not been migrated (on purpose because we should switch to fs_storage)
    env.cr.execute(
        """
    SELECT * FROM storage_backend
    """
    )
    storage_field = openupgrade.get_legacy_name("storage_id")
    column_names = [desc[0] for desc in env.cr.description]
    storage_backend_records = []
    for row in env.cr.fetchall():
        storage_backend_records.append(dict(zip(column_names, row, strict=False)))
    fs_storage = env["fs.storage"]

    for record in storage_backend_records:
        code = env["ir.http"]._slugify(record.get("name")).replace("-", "_")
        if fs_storage.search([("code", "=", code)]):
            code = "%s_%d" % (code, record.id)

        res_id = fs_storage.create(_get_storage_vals(code, record))

        env.cr.execute(
            f"UPDATE edi_backend SET {storage_field} = %s WHERE storage_id = %s",
            (res_id.id, record["id"]),
        )
