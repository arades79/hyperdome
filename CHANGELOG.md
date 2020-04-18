# Hyperdome Changelog

## 0.2.1
changed some build files so hyperdome is not flagged by antivirus on windows.

Also tweaked linux build instructions and included binary linux builds

## 0.2
A considerably more viable demo release!

#### Binary builds
 This release includes binary builds for Windows,
and the ability to build binaries for Windows and Linux.

#### Poetry script commands
The debug builds are also still available to run through new poetry script commands:
```sh
poetry run hyperdome_server --debug
poetry run hyperdome_client --debug
```

#### CLI
This release includes a more robust CLI with rudementary ability to administrate the hyperdome server.
The CLI can be initiated from either the binary build, or the poetry run target, use `--help` to see all options and commands.

Currently not all commands do what is advertised. `add` and `remove` commands on the server only give dummy output.

#### Authenticated Counselors
This release adds the ability to add counselors to a server through its CLI using the `generate` command.

This command will generate a sign-up token for a counselor to use. Send this code to a counselor and have them put the code in the *password* field when adding a new server. The counselor's client will generate a public key to use with that server to use for authentication from that point on.

#### E2EE
All chats now use end-to-end encryption for all sessions between counselor and guest. This means that the server is no longer able to read any messages during transmission! All sessions use ephemeral X448 key-pairs to create send and recieve key ratchets used to create unique AES-128 and SHA2-128 HMAC keys for every message sent.

#### And much more!
All the PRs and issues unique to this release can be viewed at:
https://github.com/arades79/hyperdome/milestone/2


## 0.1
First release. Only runnable via dev scripts, does not provide dependencies.
Offers baseline functionality, for demonstration purposes only.

View the full set of PRs and issues tied to this release at:
https://github.com/arades79/hyperdome/milestone/1
