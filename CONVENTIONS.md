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
