# V0.1 in-game acceptance

The workflow is deliberately manual-only. A PR or push never writes an EULA acceptance file.

After reviewing the Minecraft EULA, run the GitHub Actions workflow "V0.1 Creature In-Game Acceptance" and explicitly check its accept_eula input. The workflow generates a fresh creature JAR, copies it into a disposable directory, adds the GameTest source set there, and runs server plus client GameTests.

The server test checks entity registration, attributes and the registered right-click callback. The client test creates a singleplayer world, spawns the generated creature, waits for client replication and captures a screenshot after the client has received the entity.

The generated distributable project is not modified by the test preparation script. The EULA file and GameTest source set exist only in the disposable copy.
