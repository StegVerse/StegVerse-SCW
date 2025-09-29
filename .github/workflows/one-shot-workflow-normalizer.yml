name: One-Shot Workflow Normalizer
on: workflow_dispatch
jobs:
  tidy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/validate_and_fix.py --apply || true
      - name: Commit normalized workflows
        run: |
          git config user.name "normalizer-bot"
          git config user.email "bot@stegverse.local"
          git add .github/workflows/*.yml .github/workflows/*.yaml || true
          git commit -m "normalize(workflows): auto-fixes (shebang, quotes, secrets, heredoc trims)" || echo "no changes"
          git push
