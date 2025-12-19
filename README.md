# Turbo Monorepo

This is the monorepo for the Ardrive Turbo Upload and Payment Service SDKs and related tools.

## Packages

- [`turbo-python-sdk`](./packages/turbo-python-sdk) - Python SDK for interacting with the Turbo service

## Development

This monorepo uses:
- **Changesets** for version management and changelog generation
- **npm workspaces** for managing multiple packages

### Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Make changes to packages as needed

3. Create a changeset to describe your changes:
   ```bash
   npm run changeset
   ```

4. Version packages and update changelogs:
   ```bash
   npm run version
   ```

5. Publish packages:
   ```bash
   npm run release
   ```

## License

MIT License - see [LICENSE](./LICENSE) for details.
