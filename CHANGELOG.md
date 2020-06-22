# Hyperdome Changelog

For full list of code changes in each verison, [refer to our milestones](https://github.com/arades79/hyperdome/milestone/)

## 0.3.0

This update is mostly under-the-covers changes to help maintain secure practices and simplify future development.

0.3.0 clients and servers are inter-compatible.

#### macOS Support and Binaries
Updated build files and dependencies to support macOS clients.
Hyperdome server currently runs on macOS, but binaries will not be provided at this time.

#### Code Refactoring
Many core classes and functions that existed in the Onionshare codebase were removed,
and the code was simplified. These changes should make the project easier to contribute to.

Threading and UI code changes were also made in support of better testing, and better decoupling from qt.
This should help make future API changes more easily, as well as make new UI developments more quickly.
Having a decoupled client implementation will also make third party clients easier to make, or future mobile apps.

#### (optional) Comprehensive Logging
This release adds pervasive logging support to allow significantly easier debugging.
Importantly, all logging can be disabled, and/or redirected to ensure no logs are kept.
All server logging contain no user information, and messages are never logged.
A malicious server opperator adhering to license will not be capable of tracking users.

#### Unit Tests, Code Coverage, and CI
In an effort to make debugging even easier, and development faster, unit tests and automated tested is now in hyperdome!
All pull requests will now require passing all unit tests, as well as a pass from bandit, a python security linter.

Unit tests are not well-covering yet, as some older code pending removal is not tested,
and very large classes will need to be refactored before being unit testable.

#### Bundled Tor Support (Linux & BSD)
Previous issues preventing use of bundled Tor on hosts that get their Tor from a package manager have been resolved.



## 0.2.1
changed some build files so hyperdome is not flagged by antivirus on windows.

Also tweaked linux build instructions and included binary linux builds.

The linux builds included were built on WSL and could not be properly tested due to WSL limitations

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
