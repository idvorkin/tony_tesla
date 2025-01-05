# Coding conventions used in this project

For CLIs, use a Typer app.
Use `ic` for logging.
Use Rich for pretty printing.
Use Loguru for logging.
Use Typer for CLI apps.
Use Pydantic for data validation.
Use types; when using types, prefer using built-ins like `foo | None` vs `foo: Optional[str]`.
When using Typer, use the latest syntax for arguments and options.

```python
    name: Annotated[Optional[str], typer.Argument()] = None
    def main(name: Annotated[str, typer.Argument()] = "Wade Wilson"):
    lastname: Annotated[str, typer.Option(help="Last name of person to greet.")] = "",
    formal: Annotated[bool, typer.Option(help="Say hi formally.")] = False,
```

### Code Style

Prefer returning from a function vs nesting ifs.
Prefer descriptive variable names over comments.
Avoid nesting ifs, return from functions as soon as you can

### Types

Use types whenever possible.
Use the latest syntax for types (3.12)
Don't use tuples, define pydantic types for return values. Call Them FunctionReturn for the function name
<examples>
For a Single Item Return
Function: get_user_profile()
Return Type: UserProfileResponse
For Multiple Items
Function: list_users()
Return Type: UserListResponse or PaginatedUsersResponse
For Aggregated Data
Function: get_sales_summary()
Return Type: SalesSummaryResult
For Nested or Composite Data
Function: get_order_details()
Return Type: OrderDetailsResponse (which may include nested models like ProductInfo or ShippingDetails).
</examples>

### Testing

When possible update the tests to reflect the new changes.
Tests are in the test directory

### Running Tests

When running pytest, use auto mode with pytest-xdist to parallelize test execution:

```bash
pytest -n auto
```

This automatically detects the optimal number of CPU cores and distributes tests accordingly.

For debugging specific tests, run without -n flag:
```bash
pytest test_specific.py -v
```

### TUI Applications

When creating TUI (Text User Interface) applications:
- Use Textual library for TUI apps
- Include standard key bindings:
  ```python
  BINDINGS = [
      Binding("q", "quit", "Quit"),
      Binding("j", "move_down", "Down"), 
      Binding("k", "move_up", "Up"),
      Binding("?", "help", "Help")
  ]
  ```
- Include a Help screen modal that shows available commands
- Use DataTable for tabular data display:
  - When accessing DataTable columns, handle ColumnKey objects by stripping wrapper text:
    ```python
    columns = [str(col).replace("ColumnKey('", "").replace("')", "") 
              for col in table.columns.keys()]
    ```
  - Always include a key parameter when adding rows for selection tracking
  - Implement row selection handlers with `on_data_table_row_selected`

- For modal screens:
  - Inherit from ModalScreen
  - Include proper styling in on_mount:
    ```python
    def on_mount(self) -> None:
        container = self.query_one(Container)
        container.styles.align = ("center", "middle")
        container.styles.height = "auto"
        container.styles.width = "auto"
        container.styles.background = "rgba(0,0,0,0.8)"
        container.styles.padding = (2, 4)
        container.styles.border = ("solid", "white")
    ```
  - Use Container for layout management
  - Include proper error handling with loguru
  - Follow this structure for the main app:
    ```python
    class MyTUIApp(App):
        # Define bindings
        # Define compose() for layout
        # Define action methods for commands
    
    @app.command()
    def browse():
        """Browse data in an interactive TUI"""
        app = MyTUIApp()
        app.run()
    
    @logger.catch()
    def app_wrap_loguru():
        app()
    ```

### TUI Applications

When creating TUI (Text User Interface) applications:
- Use Textual library for TUI apps
- Include standard key bindings:
  ```python
  BINDINGS = [
      Binding("q", "quit", "Quit"),
      Binding("j", "move_down", "Down"), 
      Binding("k", "move_up", "Up"),
      Binding("?", "help", "Help")
  ]
  ```
- Include a Help screen modal that shows available commands
- Use DataTable for tabular data display
- Use Static widgets for text display areas
- Use Container for layout management
- Include proper error handling with loguru
- Follow this structure for the main app:
  ```python
  class MyTUIApp(App):
      # Define bindings
      # Define compose() for layout
      # Define action methods for commands
  
  @app.command()
  def browse():
      """Browse data in an interactive TUI"""
      app = MyTUIApp()
      app.run()
  
  @logger.catch()
  def app_wrap_loguru():
      app()
  ```

### Debugging

When debugging, use the `ic` library:

- Import ic at the top of files:
  ```python
  from icecream import ic
  ```

- Use ic() to debug variables and expressions:
  ```python
  # Basic variable inspection
  ic(my_variable)
  
  # Multiple variables
  ic(var1, var2, calculation_result)
  
  # Expressions
  ic(table.columns, table.row_count)
  
  # Objects and their properties
  ic(details.render()._renderable)
  
  # Before/after state changes
  ic("Before action:", current_state)
  action()
  ic("After action:", new_state)
  ```

- For test debugging, combine ic with print statements for context:
  ```python
  print("\nDEBUG: Starting test")
  ic(test_object)
  
  # Show test progress
  print("\nDEBUG: After action")
  ic(result)
  ```

- When debugging async code, mark important points:
  ```python
  ic("Before await")
  await async_operation()
  ic("After await")
  ```

### Testing TUI Applications

When testing Textual TUI applications:

- Use pytest-asyncio and mark tests:
  ```python
  pytestmark = pytest.mark.asyncio
  ```

- Include standard test fixtures:
  ```python
  @pytest.fixture
  async def app():
      """Create test app instance."""
      return MyTUIApp()
  ```

- Use app.run_test() context manager:
  ```python
  async def test_something(app):
      async with app.run_test() as pilot:
          # Test code here
  ```

- Add comprehensive debugging:
  ```python
  # Debug widget tree
  print(f"DEBUG: App widgets: {app.query('*')}")
  
  # Debug specific components
  table = app.query_one(DataTable)
  print(f"Table properties: {table.columns}")
  
  # Debug events and state changes
  print(f"Before action: {current_state}")
  await pilot.press("key")
  print(f"After action: {new_state}")
  ```

- Test widget queries and selections:
  ```python
  table = app.query_one(DataTable)
  details = app.query_one("#details", Static)
  ```

- Allow time for UI updates:
  ```python
  await pilot.pause()
  ```

- Test modal screens:
  ```python
  await pilot.press("?")  # Open modal
  assert isinstance(app.screen, HelpScreen)
  await pilot.press("escape")  # Close modal
  ```

- Test DataTable operations:
  - Extract column information:
    ```python
    columns = [str(col).replace("ColumnKey('", "").replace("')", "") 
              for col in table.columns.keys()]
    ```
  - Test row selection:
    ```python
    table.move_cursor(row=0)
    table.action_select_cursor()
    ```

- Include error handling in tests:
  ```python
  try:
      # Test code
  except Exception as e:
      print(f"DEBUG: Test failed with error: {e}")
      print(f"App state: {app.query('*')}")
      raise
  ```

- Test keyboard navigation:
  ```python
  await pilot.press("j")  # Down
  await pilot.press("k")  # Up
  await pilot.press("q")  # Quit
  ```

- Verify widget content:
  ```python
  content = widget.render()._renderable
  assert "expected text" in str(content)
  ```

### Tony VAPI Configuration

To get the latest Tony VAPI configuration settings:

```bash
tony export-vapi-tony-config
```

This command exports the current configuration which can be used as a reference for updating `tony_assistant_spec.json`. Key configuration areas include:

- Voice settings (voiceId, provider, stability, similarityBoost)
- Model configuration (model, maxTokens, temperature)
- Server and client message types
- End call settings and phrases
- Transcriber configuration
- Analysis plan settings

When updating the configuration, ensure compatibility between the exported settings and your local `tony_assistant_spec.json`.

- Use `uv` instead of `pip` for package management.
- Ensure to update dependencies in `pyproject.toml` when adding new packages or updating existing ones.

### Fixing Tests

When fixing tests, the goal is to be as efficient as possible. Here are some guidelines:

- **Unit Tests First**: Ensure unit tests pass before moving on to integration tests.
- **Integration Before E2E**: Run integration tests before end-to-end tests to catch issues early.
- **Parallel Execution**: Run tests in parallel to save time.
- **Iterate on Failing Tests**: If iterating on a failing test, only run that specific test instead of the entire suite.
  - Example: Use `pytest tests/unit/test_specific.py -v` to run a specific unit test.
  - For integration tests, use `pytest tests/integration/test_specific.py -v`.
  - For end-to-end tests, use `pytest tests/e2e/test_specific.py -v`.

### Git Commit Messages

When creating git commit messages:
- Use multi-line messages for meaningful commits
- First line is a summary (50 chars or less) starting with type: (e.g., "feat:", "fix:", "test:")
- Leave a blank line after the summary
- Follow with bullet points of specific changes

Since the tools don't support direct newlines, use $' syntax with \n for multi-line messages:

```bash
git commit -m $'feat: Add new feature\n\n- Add X functionality\n- Update Y module\n- Fix Z issue'
```

Types for the summary line:
- feat: New feature
- fix: Bug fix
- test: Adding or updating tests
- docs: Documentation only changes
- refactor: Code change that neither fixes a bug nor adds a feature
- style: Changes that do not affect the meaning of the code
- chore: Changes to the build process or auxiliary tools

### Git Commit Best Practices

Before committing changes:
1. Review modified files using file reading capabilities rather than git diff
2. Run tests to ensure they pass, following the test instructions above:
   - Run unit tests first
   - Use parallel execution with `pytest -n auto`
   - For iterating on specific tests, use the test file path:
     ```bash
     # Example: Run only the specific test you're working on
     pytest tests/integration/test_specific.py -v -k test_name
     ```
3. Run `git status` to review all modified files
4. Verify that only intended files are included
5. Use `git add` to stage specific files rather than `git add .`
6. Double-check staged files with `git status` again before committing
7. For multi-file changes, ensure all related files are included (e.g., both implementation and tests)
8. Exclude temporary files, logs, and other unrelated changes
