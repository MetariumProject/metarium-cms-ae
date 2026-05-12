#!/usr/bin/env python3
"""CLI script to set the CMS administrator address.

Usage:
    python setup_admin.py <ss58_address>
    python setup_admin.py --generate
"""

import os
import sys


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__.strip())
        sys.exit(0)

    arg = sys.argv[1]

    if arg == '--generate':
        from substrateinterface import Keypair
        keypair = Keypair.create_from_mnemonic(Keypair.generate_mnemonic())
        print(f"Mnemonic:  {keypair.mnemonic}")
        print(f"Address:   {keypair.ss58_address}")
        address = keypair.ss58_address
    else:
        # Validate the provided SS58 address
        from substrateinterface import Keypair
        address = arg
        try:
            Keypair(ss58_address=address)
        except Exception as exc:
            print(f"Error: Invalid SS58 address '{address}': {exc}", file=sys.stderr)
            sys.exit(1)

    # Initialize NDB client
    from google.cloud import ndb

    project = os.environ.get('GOOGLE_CLOUD_PROJECT', 'metarium-cms-ae')
    try:
        ndb_client = ndb.Client(project=project)
    except Exception:
        import google.auth.credentials

        class _AnonymousCredentials(google.auth.credentials.Credentials):
            def refresh(self, request):
                pass

            @property
            def valid(self):
                return True

        ndb_client = ndb.Client(project=project, credentials=_AnonymousCredentials())

    from models.acl_models import CMSConfig

    with ndb_client.context():
        CMSConfig.set_admin(address)

    print(f"\n✓ Admin address set to: {address}")
    print(f"  Project: {project}")

    emulator = os.environ.get('DATASTORE_EMULATOR_HOST')
    if emulator:
        print(f"  Datastore emulator: {emulator}")
    else:
        print("  Using production Datastore")


if __name__ == '__main__':
    main()
