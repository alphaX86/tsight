import streamlit as st
import json
import networkx as nx
from pyvis.network import Network
import os
from pathlib import Path
import datetime

# Set page configuration with custom theme
st.set_page_config(
    page_title="TSight",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .stTabs {
        padding: 10px;
        border-radius: 5px;
    }
    .stButton > button {
        width: 100%;
    }
    .graph-container {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        background-color: white;
    }
    .metadata-container {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .st-emotion-cache-16idsys p {
        font-size: 16px;
        line-height: 1.5;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------- Constants ------------------
DATABASE_TYPES = [
    "HIVE",
    "Oracle", 
    "Snowflake",
    "PostgreSQL",
    "MySQL",
    "SQL Server",
    "BigQuery",
    "Redshift",
    "Teradata",
    "DB2",
    "Cassandra",
    "MongoDB",
    "Spark",
    "Delta Lake",
    "Iceberg",
    "Other"
]

# Color mapping for different database types
DATABASE_TYPE_COLORS = {
    "HIVE": "#FF9800",
    "Oracle": "#F44336", 
    "Snowflake": "#2196F3",
    "PostgreSQL": "#336791",
    "MySQL": "#4479A1",
    "SQL Server": "#CC2927",
    "BigQuery": "#4285F4",
    "Redshift": "#8C4FFF",
    "Teradata": "#F37440",
    "DB2": "#1F70C1",
    "Cassandra": "#1287B1",
    "MongoDB": "#47A248",
    "Spark": "#E25A1C",
    "Delta Lake": "#00ADD4",
    "Iceberg": "#3F7CAC",
    "Other": "#9E9E9E"
}

# ---------------- Data Models ------------------
class Table:
    def __init__(self, name, schema, description="", autosys_jobs=None, table_type="Other"):
        self.name = name
        self.schema = schema
        self.description = description
        self.table_type = table_type  # Database type (HIVE, Oracle, Snowflake, etc.)
        self.autosys_jobs = autosys_jobs or []  # List of Autosys job names associated with this table
        self.columns = []  # List of Column objects
        self.quality_score = 0  # Data quality score (0-100)
        self.last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class Column:
    def __init__(self, name, data_type, description="", source_columns=None):
        self.name = name
        self.data_type = data_type
        self.description = description
        self.source_columns = source_columns or []  # List of source columns in format "table.column"
        self.quality_score = 0  # Data quality score (0-100)

class Transformation:
    def __init__(self, name, transformation_type, input_tables, output_tables, logic, description="", column_mappings=None, autosys_jobs=None):
        self.name = name
        self.transformation_type = transformation_type
        self.input_tables = input_tables  # List of table names
        self.output_tables = output_tables  # List of table names
        self.logic = logic
        self.description = description
        self.column_mappings = column_mappings or []  # List of column mappings
        self.autosys_jobs = autosys_jobs or []  # List of Autosys job names associated with this transformation
        self.created_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class ColumnMapping:
    def __init__(self, source_table, source_column, target_table, target_column, transformation_rule=""):
        self.source_table = source_table
        self.source_column = source_column
        self.target_table = target_table
        self.target_column = target_column
        self.transformation_rule = transformation_rule

# ---------------- Session State Initialization ------------------
if 'tables' not in st.session_state:
    st.session_state.tables = []
    
if 'transformations' not in st.session_state:
    st.session_state.transformations = []
    
if 'selected_table_index' not in st.session_state:
    st.session_state.selected_table_index = None
    
if 'selected_transformation_index' not in st.session_state:
    st.session_state.selected_transformation_index = None

if 'focus_entity' not in st.session_state:
    st.session_state.focus_entity = None
    
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "Tables"

# ---------------- Utility Functions ------------------
def update_quality_scores():
    """Update quality scores for tables and columns based on completeness of metadata"""
    for table in st.session_state.tables:
        # Calculate table quality score
        quality_sum = 0
        for column in table.columns:
            # Column metrics - completeness of metadata
            has_description = 10 if column.description else 0
            has_data_type = 10 if column.data_type else 0
            has_sources = 10 if column.source_columns else 0
            
            column.quality_score = min(100, has_description + has_data_type + has_sources)
            quality_sum += column.quality_score
        
        # Table score is average of column scores plus table metadata
        if table.columns:
            avg_column_score = quality_sum / len(table.columns)
            has_description = 20 if table.description else 0
            table.quality_score = min(100, int(avg_column_score * 0.8 + has_description))
        else:
            has_description = 20 if table.description else 0
            table.quality_score = has_description

def search_lineage(query, tables, transformations):
    """Search through tables, columns and transformations"""
    results = {"tables": [], "columns": [], "transformations": []}
    
    query = query.lower()
    
    # Search in tables
    for table in tables:
        # Check table properties, table type, and Autosys jobs
        table_type = getattr(table, 'table_type', 'Other')
        autosys_match = any(query in job.lower() for job in (table.autosys_jobs if hasattr(table, 'autosys_jobs') and table.autosys_jobs else []))
        table_type_match = query in table_type.lower()
        
        if (query in table.name.lower() or 
            query in table.description.lower() or 
            query in table.schema.lower() or 
            table_type_match or
            autosys_match):
            results["tables"].append({
                "name": table.name,
                "schema": table.schema,
                "description": table.description,
                "table_type": table_type,
                "type": "table"
            })
        
        # Search in columns
        for column in table.columns:
            if query in column.name.lower() or query in column.description.lower() or query in column.data_type.lower():
                results["columns"].append({
                    "name": f"{table.name}.{column.name}",
                    "data_type": column.data_type,
                    "description": column.description,
                    "table": table.name,
                    "type": "column"
                })
    
    # Search in transformations
    for transformation in transformations:
        # Check transformation properties and Autosys jobs
        autosys_match = any(query in job.lower() for job in (transformation.autosys_jobs if hasattr(transformation, 'autosys_jobs') and transformation.autosys_jobs else []))
        if (query in transformation.name.lower() or 
            query in transformation.description.lower() or
            query in transformation.logic.lower() or
            autosys_match):
            results["transformations"].append({
                "name": transformation.name,
                "type": transformation.transformation_type,
                "description": transformation.description,
                "input_tables": transformation.input_tables,
                "output_tables": transformation.output_tables
            })
    
    return results

def create_lineage_graph(tables, transformations, include_columns=False, focus_entity=None):
    """Create a networkx graph representing data lineage"""
    G = nx.DiGraph()
    
    # Set node colors
    node_colors = {
        'table': '#4CAF50',     # Green for tables
        'column': '#2196F3',    # Blue for columns
        'transformation': '#FFC107'  # Yellow for transformations
    }

    # Add tables as nodes
    for table in tables:
        # Skip if we're focusing on a specific table/column and this isn't relevant
        if focus_entity and not (focus_entity == table.name or 
                                any(focus_entity == f"{table.name}.{col.name}" for col in table.columns)):
            continue
            
        # Create tooltip with table type, Autosys jobs and other information
        tooltip_text = f"Type: {getattr(table, 'table_type', 'Other')}\nSchema: {table.schema}\n{table.description}"
        if hasattr(table, 'autosys_jobs') and table.autosys_jobs:
            tooltip_text += f"\nAutosys Jobs: {', '.join(table.autosys_jobs)}"
        
        # Get color based on table type
        table_color = DATABASE_TYPE_COLORS.get(getattr(table, 'table_type', 'Other'), DATABASE_TYPE_COLORS['Other'])
            
        G.add_node(table.name, 
                  label=table.name,
                  title=tooltip_text, 
                  shape="box",
                  color=table_color)
        
        if include_columns:
            for column in table.columns:
                col_node_id = f"{table.name}.{column.name}"
                G.add_node(
                    col_node_id,
                    label=column.name,
                    title=f"Type: {column.data_type}\nDescription: {column.description}",
                    shape="ellipse",
                    color=node_colors['column'],
                    size=10  # Smaller size for columns
                )
                G.add_edge(table.name, col_node_id)

    # Add edges based on transformations
    for transformation in transformations:
        # Add transformation as a node if column-level lineage is enabled
        if include_columns:
            # Create tooltip with Autosys jobs information
            tooltip_text = f"Type: {transformation.transformation_type}\nDescription: {transformation.description}"
            if hasattr(transformation, 'autosys_jobs') and transformation.autosys_jobs:
                tooltip_text += f"\nAutosys Jobs: {', '.join(transformation.autosys_jobs)}"
                
            G.add_node(
                transformation.name,
                label=transformation.name,
                title=tooltip_text,
                shape="diamond",
                color=node_colors['transformation']
            )
            
            # Connect based on column mappings if available
            if hasattr(transformation, 'column_mappings') and transformation.column_mappings:
                for mapping in transformation.column_mappings:
                    source_id = f"{mapping.source_table}.{mapping.source_column}"
                    target_id = f"{mapping.target_table}.{mapping.target_column}"
                    
                    # Check if these nodes are in the graph (they might be filtered out)
                    if source_id in G and target_id in G:
                        G.add_edge(source_id, transformation.name, title=mapping.transformation_rule)
                        G.add_edge(transformation.name, target_id)
            else:
                # Default connections if no column mappings
                for input_table in transformation.input_tables:
                    if input_table in G:
                        G.add_edge(input_table, transformation.name)
                        
                for output_table in transformation.output_tables:
                    if output_table in G:
                        G.add_edge(transformation.name, output_table)
        else:
            # Table-level lineage only
            for input_table in transformation.input_tables:
                for output_table in transformation.output_tables:
                    if input_table in G and output_table in G:
                        G.add_edge(input_table, output_table, 
                                  label=transformation.name, 
                                  title=transformation.description)

    return G

def display_graph(graph, physics=True, layout="hierarchical", theme="light", options=None): 
    """Render the lineage graph using pyvis Network with enhanced options"""
    # Set up height and width for better visibility
    height = "700px"
    width = "100%"
    
    # Create Network object
    nt = Network(height, width, notebook=True, heading="", bgcolor=None)
    
    # Apply theme colors
    if theme == "dark":
        nt.bgcolor = "#222222"
        nt.font_color = "white"
    else:
        nt.bgcolor = "#ffffff"
        nt.font_color = "black"
    
    # Add the graph
    nt.from_nx(graph)
    
    # Apply custom options if provided
    if options:
        nt.options = options
    
    # Generate the HTML file
    html_path = "lineage_graph.html"
    nt.save_graph(html_path)
    
    # Display the HTML using streamlit components
    with open(html_path, 'r', encoding='utf-8') as f:
        html_data = f.read()
        
    # Enhance the HTML with responsive container
    enhanced_html = f"""
        <div style="width:100%; height:700px; border:none; border-radius:5px; overflow:hidden;">
            {html_data}
        </div>
    """

    st.components.v1.html(enhanced_html, height=700, scrolling=False)

def export_data(tables, transformations, filepath):
    """Export tables and transformations to a JSON file"""
    data = {
        "tables": [
            {
                **table.__dict__,
                "columns": [col.__dict__ for col in table.columns],  # Include column data
            }
            for table in tables
        ],
        "transformations": [
            {
                **transformation.__dict__,
                "column_mappings": [mapping.__dict__ for mapping in transformation.column_mappings] 
                if hasattr(transformation, "column_mappings") else []
            }
            for transformation in transformations
        ],
    }
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
        st.success(f"Data exported to {filepath}")
    except Exception as e:
        st.error(f"Error exporting data: {e}")

def import_data(filepath):
    """Import tables and transformations from a JSON file"""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)

        tables = []
        for table_data in data.get("tables", []):
            table = Table(
                name=table_data["name"],
                schema=table_data["schema"],
                description=table_data["description"],
                autosys_jobs=table_data.get("autosys_jobs", []),
                table_type=table_data.get("table_type", "Other")  # Backward compatibility
            )
            if "quality_score" in table_data:
                table.quality_score = table_data["quality_score"]
            if "last_updated" in table_data:
                table.last_updated = table_data["last_updated"]
                
            table.columns = []
            for col_data in table_data.get("columns", []):
                column = Column(
                    name=col_data["name"],
                    data_type=col_data["data_type"],
                    description=col_data["description"],
                    source_columns=col_data.get("source_columns", [])
                )
                if "quality_score" in col_data:
                    column.quality_score = col_data["quality_score"]
                table.columns.append(column)
            tables.append(table)

        transformations = []
        for trans_data in data.get("transformations", []):
            transformation = Transformation(
                name=trans_data["name"],
                transformation_type=trans_data["transformation_type"],
                input_tables=trans_data["input_tables"],
                output_tables=trans_data["output_tables"],
                logic=trans_data["logic"],
                description=trans_data["description"],
                autosys_jobs=trans_data.get("autosys_jobs", [])
            )
            
            # Handle column mappings
            if "column_mappings" in trans_data:
                transformation.column_mappings = []
                for mapping_data in trans_data["column_mappings"]:
                    mapping = ColumnMapping(
                        source_table=mapping_data["source_table"],
                        source_column=mapping_data["source_column"],
                        target_table=mapping_data["target_table"],
                        target_column=mapping_data["target_column"],
                        transformation_rule=mapping_data.get("transformation_rule", "")
                    )
                    transformation.column_mappings.append(mapping)
            
            transformations.append(transformation)
        
        # Update session state
        st.session_state.tables = tables
        st.session_state.transformations = transformations
            
        st.success(f"Data imported from {filepath}")

    except FileNotFoundError:
        st.error(f"File not found: {filepath}")
    except json.JSONDecodeError:
        st.error(f"Invalid JSON file: {filepath}")
    except Exception as e:
        st.error(f"Error importing data: {e}")

def get_file_path(mode="save"):
    """File browser for selecting import/export paths"""
    current_dir = os.getcwd()
    st.write(f"Current directory: {current_dir}")
    
    # Allow navigating up
    col1, col2 = st.columns([1, 5])
    if col1.button("↑ Up"):
        parent_dir = os.path.dirname(current_dir)
        os.chdir(parent_dir)
        st.rerun()
    
    # List directories and json files
    directories = [d for d in os.listdir() if os.path.isdir(d)]
    json_files = [f for f in os.listdir() if f.endswith('.json') and os.path.isfile(f)]
    
    # Navigate to directories
    if directories:
        selected_dir = col2.selectbox("Navigate to:", ["<Select a directory>"] + directories)
        if selected_dir != "<Select a directory>":
            os.chdir(os.path.join(current_dir, selected_dir))
            st.rerun()
    
    # When importing, select from existing files
    if mode == "import" and json_files:
        selected_file = st.selectbox("Select file to import:", ["<Select a file>"] + json_files)
        if selected_file != "<Select a file>":
            return os.path.join(current_dir, selected_file)
    
    # For saving, enter filename
    if mode == "save":
        filename = st.text_input("Enter filename:", "data_lineage.json")
        if filename:
            if not filename.endswith('.json'):
                filename += '.json'
            return os.path.join(current_dir, filename)
    
    return None

def generate_sample_data():
    """Generate sample tables and transformations for demo purposes"""
    # Create sample tables
    sample_tables = [
        Table("customers", "sales", "Customer information table", ["JOB_LOAD_CUSTOMERS", "JOB_VALIDATE_CUSTOMERS"], "PostgreSQL"),
        Table("orders", "sales", "Order details table", ["JOB_LOAD_ORDERS", "JOB_PROCESS_ORDERS"], "MySQL"),
        Table("products", "inventory", "Product information table", ["JOB_UPDATE_PRODUCTS"], "Oracle"),
        Table("sales_summary", "analytics", "Aggregated sales data", ["JOB_GENERATE_SALES_SUMMARY", "JOB_EXPORT_ANALYTICS"], "Snowflake")
    ]
    
    # Add columns to tables
    sample_tables[0].columns = [
        Column("customer_id", "INT", "Primary key"),
        Column("customer_name", "VARCHAR", "Full name"),
        Column("email", "VARCHAR", "Email address")
    ]
    
    sample_tables[1].columns = [
        Column("order_id", "INT", "Primary key"),
        Column("customer_id", "INT", "Foreign key to customers"),
        Column("product_id", "INT", "Foreign key to products"),
        Column("order_date", "DATE", "Date of purchase"),
        Column("amount", "DECIMAL", "Purchase amount")
    ]
    
    sample_tables[2].columns = [
        Column("product_id", "INT", "Primary key"),
        Column("product_name", "VARCHAR", "Product name"),
        Column("category", "VARCHAR", "Product category"),
        Column("price", "DECIMAL", "Unit price")
    ]
    
    sample_tables[3].columns = [
        Column("date", "DATE", "Sales date"),
        Column("product_id", "INT", "Product identifier"),
        Column("total_sales", "DECIMAL", "Total sales amount"),
        Column("units_sold", "INT", "Number of units sold")
    ]
    
    # Add source columns
    sample_tables[1].columns[1].source_columns = ["customers.customer_id"]
    sample_tables[1].columns[2].source_columns = ["products.product_id"]
    sample_tables[3].columns[1].source_columns = ["products.product_id"]
    sample_tables[3].columns[2].source_columns = ["orders.amount"]
    sample_tables[3].columns[3].source_columns = ["orders.product_id"]
    
    # Create sample transformations
    sample_transformations = [
        Transformation(
            "order_processing",
            "SQL",
            ["customers", "products"],
            ["orders"],
            "INSERT INTO orders (customer_id, product_id, order_date, amount)\nSELECT c.customer_id, p.product_id, CURRENT_DATE, p.price\nFROM customers c, products p\nWHERE c.customer_id = ?",
            "Process new orders",
            autosys_jobs=["JOB_ORDER_ETL", "JOB_ORDER_VALIDATION"]
        ),
        Transformation(
            "sales_aggregation",
            "SQL",
            ["orders", "products"],
            ["sales_summary"],
            "INSERT INTO sales_summary (date, product_id, total_sales, units_sold)\nSELECT DATE(o.order_date), o.product_id, SUM(o.amount), COUNT(*)\nFROM orders o\nJOIN products p ON o.product_id = p.product_id\nGROUP BY DATE(o.order_date), o.product_id",
            "Aggregate sales data daily",
            autosys_jobs=["JOB_DAILY_AGGREGATION", "JOB_SALES_SUMMARY"]
        )
    ]
    
    # Add column mappings
    sample_transformations[0].column_mappings = [
        ColumnMapping("customers", "customer_id", "orders", "customer_id", "Direct copy"),
        ColumnMapping("products", "product_id", "orders", "product_id", "Direct copy"),
        ColumnMapping("products", "price", "orders", "amount", "Direct copy")
    ]
    
    sample_transformations[1].column_mappings = [
        ColumnMapping("orders", "order_date", "sales_summary", "date", "Convert to date"),
        ColumnMapping("orders", "product_id", "sales_summary", "product_id", "Direct copy"),
        ColumnMapping("orders", "amount", "sales_summary", "total_sales", "Sum aggregation"),
        ColumnMapping("orders", "product_id", "sales_summary", "units_sold", "Count aggregation")
    ]
    
    # Update session state
    st.session_state.tables = sample_tables
    st.session_state.transformations = sample_transformations
    
    # Update quality scores
    update_quality_scores()

# ---------------- Main UI ------------------
def main():
    # Sidebar with logo and navigation
    with st.sidebar:
        st.title("🔄 TSight")
        st.markdown("---")
        
        # Navigation tabs in sidebar
        selected_tab = st.session_state.active_tab

        if st.button("Tables", key="tab_tables"):
            selected_tab = "Tables"
        if st.button("Transformations", key="tab_transformations"):
            selected_tab = "Transformations"
        if st.button("Lineage Graph", key="tab_lineage_graph"):
            selected_tab = "Lineage Graph"
        if st.button("Import/Export", key="tab_import_export"):
            selected_tab = "Import/Export"
        if st.button("Search", key="tab_search"):
            selected_tab = "Search"

        st.session_state.active_tab = selected_tab
        
        st.markdown("---")
        with st.container():
            st.markdown("### Quick Stats")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Tables", len(st.session_state.tables))
            with col2:
                st.metric("Transformations", len(st.session_state.transformations))
        
        st.markdown("---")
        if st.button("Generate Sample Data", use_container_width=True):
            generate_sample_data()
            st.success("Sample data generated!")
            st.rerun()

    # Initialize saved_views if not exists
    if 'saved_views' not in st.session_state:
        st.session_state.saved_views = []
    
    # Main content area based on selected tab
    
    if selected_tab == "Tables":
        render_tables_tab()
    elif selected_tab == "Transformations":
        render_transformations_tab()
    elif selected_tab == "Lineage Graph":
        render_lineage_graph_tab()
    elif selected_tab == "Import/Export":
        render_import_export_tab()
    else:
        render_search_tab()

# ---------------- Tab Rendering Functions ------------------
def render_tables_tab():
    st.header("Table Management")
    
    # Handle state updates first
    if 'table_to_edit' not in st.session_state:
        st.session_state.table_to_edit = None
    if 'column_to_edit' not in st.session_state:
        st.session_state.column_to_edit = {}
        
    # Create/Edit Table Form
    with st.expander("Create/Edit Table", expanded=True if st.session_state.selected_table_index is not None else False):
        with st.form("table_form"):
            if st.session_state.selected_table_index is not None:
                table = st.session_state.tables[st.session_state.selected_table_index]
                table_name = st.text_input("Table Name", value=table.name)
                table_schema = st.text_input("Table Schema", value=table.schema)
                table_description = st.text_area("Table Description", value=table.description)
                
                # Table type selection for editing
                current_table_type = getattr(table, 'table_type', 'Other')
                table_type_index = DATABASE_TYPES.index(current_table_type) if current_table_type in DATABASE_TYPES else DATABASE_TYPES.index('Other')
                table_type = st.selectbox("Table Type", DATABASE_TYPES, index=table_type_index,
                                        help="Select the database type for this table")
                
                # Handle Autosys jobs field for editing
                autosys_jobs_text = "\n".join(table.autosys_jobs) if hasattr(table, 'autosys_jobs') and table.autosys_jobs else ""
                autosys_jobs_input = st.text_area("Autosys Jobs (one per line)", value=autosys_jobs_text, 
                                                help="Enter each Autosys job name on a separate line")
            else:
                table_name = st.text_input("Table Name")
                table_schema = st.text_input("Table Schema")
                table_description = st.text_area("Table Description")
                table_type = st.selectbox("Table Type", DATABASE_TYPES, index=DATABASE_TYPES.index('Other'),
                                        help="Select the database type for this table")
                autosys_jobs_input = st.text_area("Autosys Jobs (one per line)", 
                                                help="Enter each Autosys job name on a separate line")
            
            submitted = st.form_submit_button("Create/Update Table")
            if submitted:
                if not table_name or not table_schema:
                    st.error("Table Name and Schema are required.")
                else:
                    # Process Autosys jobs
                    autosys_jobs = [job.strip() for job in autosys_jobs_input.split('\n') if job.strip()]
                    
                    if st.session_state.selected_table_index is not None:
                        # Update existing table
                        st.session_state.tables[st.session_state.selected_table_index].name = table_name
                        st.session_state.tables[st.session_state.selected_table_index].schema = table_schema
                        st.session_state.tables[st.session_state.selected_table_index].description = table_description
                        st.session_state.tables[st.session_state.selected_table_index].table_type = table_type
                        st.session_state.tables[st.session_state.selected_table_index].autosys_jobs = autosys_jobs
                        st.session_state.tables[st.session_state.selected_table_index].last_updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        st.session_state.selected_table_index = None
                        st.success(f"Table '{table_name}' updated!")
                        st.rerun()
                    else:
                        # Create new table
                        new_table = Table(table_name, table_schema, table_description, autosys_jobs, table_type)
                        st.session_state.tables.append(new_table)
                        st.success(f"Table '{table_name}' created!")
                        st.rerun()

    # Display Existing Tables
    st.subheader("Existing Tables")
    if st.session_state.tables:
        for i, table in enumerate(st.session_state.tables):
            col1, col2, col3, col4 = st.columns([0.6, 0.15, 0.15, 0.1])
            
            # Get table type for display and color
            table_type = getattr(table, 'table_type', 'Other')
            table_color = DATABASE_TYPE_COLORS.get(table_type, DATABASE_TYPE_COLORS['Other'])
            
            table_info = f"<b>{table.name}</b> (Schema: {table.schema})"
            table_info += f"\n  📊 <b>Type</b>: {table_type}"
            if hasattr(table, 'autosys_jobs') and table.autosys_jobs:
                table_info += f"<br>  🔄 <b>Autosys Jobs</b>: {', '.join(table.autosys_jobs)}"
            
            # Add colored indicator for table type
            col1.markdown(f'<div style="border-left: 4px solid {table_color}; padding-left: 10px;">{table_info}</div>', 
                         unsafe_allow_html=True)
            col4.metric("Quality", f"{table.quality_score}%")
            
            # Edit button now sets the selected_table_index
            if col2.button("Edit", key=f"edit_table_{i}"):
                st.session_state.selected_table_index = i
                st.rerun()
                
            if col3.button("Delete", key=f"delete_table_{i}"):
                if st.session_state.get(f"confirm_delete_table_{i}", False):
                    st.session_state.tables.pop(i)
                    st.success(f"Table '{table.name}' deleted!")
                    st.rerun()
                else:
                    st.session_state[f"confirm_delete_table_{i}"] = True
                    st.warning(f"Click 'Delete' again to confirm deleting table '{table.name}'")

            # Column Management
            with st.expander(f"Manage Columns for {table.name}"):
                with st.form(f"column_form_{table.name}"):
                    column_name = st.text_input("Column Name", key=f"col_name_{table.name}")
                    column_data_type = st.text_input("Data Type", key=f"col_type_{table.name}")
                    column_description = st.text_area("Column Description", key=f"col_desc_{table.name}")
                    
                    # Enhanced column lineage with source column selection
                    source_columns = []
                    if st.session_state.tables:
                        all_columns = []
                        for src_table in st.session_state.tables:
                            for col in src_table.columns:
                                all_columns.append(f"{src_table.name}.{col.name}")
                        
                        source_columns = st.multiselect(
                            "Source Columns", 
                            all_columns,
                            key=f"src_cols_{table.name}"
                        )
                    
                    column_submitted = st.form_submit_button("Add Column")

                    if column_submitted:
                        if not column_name or not column_data_type:
                            st.error("Column Name and Data Type are required.")
                        else:
                            new_column = Column(column_name, column_data_type, column_description, source_columns)
                            table.columns.append(new_column)
                            st.success(f"Column '{column_name}' added to '{table.name}'")
                            update_quality_scores()
                            st.rerun()

                # Display existing columns
                if table.columns:
                    for j, column in enumerate(table.columns):
                        col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
                        col_text = f"- **{column.name}**: {column.data_type} ({column.description})"
                        if hasattr(column, "quality_score"):
                            col_text += f" - Quality: {column.quality_score}%"
                        col1.write(col_text)
                        
                        # Show source columns if any
                        if column.source_columns:
                            col1.write(f"  Sources: {', '.join(column.source_columns)}")
                            
                        if col2.button("Edit", key=f"edit_col_{table.name}_{j}"):
                            st.session_state.column_to_edit = {
                                'table_index': i, # Store table index
                                'table_name': table.name, # Keep for potential direct access if needed, though index is primary
                                'col_index': j
                            }
                            st.rerun()
                            
                        if col3.button("Delete", key=f"delete_col_{table.name}_{j}"):
                            table.columns.pop(j)
                            st.success(f"Column '{column.name}' deleted!")
                            update_quality_scores()
                            st.rerun()
                else:
                    st.write("No columns defined yet.")
    else:
        st.info("No tables defined yet. Click 'Create/Edit Table' to add one, or use 'Generate Sample Data' in the sidebar.")

    # --- Moved Edit Column Form ---
    if st.session_state.get('column_to_edit') and st.session_state.column_to_edit:
        edit_info = st.session_state.column_to_edit
        table_index = edit_info.get('table_index')
        
        if table_index is not None and 0 <= table_index < len(st.session_state.tables):
            table_for_col_edit = st.session_state.tables[table_index]
            col_index = edit_info.get('col_index')

            if col_index is not None and 0 <= col_index < len(table_for_col_edit.columns):
                column_to_edit_obj = table_for_col_edit.columns[col_index]
                
                st.subheader(f"Edit Column: {column_to_edit_obj.name} (from Table: {table_for_col_edit.name})")
                # Use a unique key for the form to avoid conflicts if multiple edit forms were ever simultaneously possible (though current logic prevents this)
                with st.form(f"edit_col_form_standalone_{table_for_col_edit.name}_{col_index}"):
                    new_col_name = st.text_input("Column Name", value=column_to_edit_obj.name, key=f"edit_col_name_{table_for_col_edit.name}_{col_index}")
                    new_col_type = st.text_input("Data Type", value=column_to_edit_obj.data_type, key=f"edit_col_type_{table_for_col_edit.name}_{col_index}")
                    new_col_desc = st.text_area("Description", value=column_to_edit_obj.description, key=f"edit_col_desc_{table_for_col_edit.name}_{col_index}")
                    
                    all_available_columns_for_source = []
                    for src_tbl_idx, src_table_obj in enumerate(st.session_state.tables):
                        for src_col_idx, src_col_obj in enumerate(src_table_obj.columns):
                            # Prevent self-referencing a column to itself as a source
                            if not (src_tbl_idx == table_index and src_col_idx == col_index):
                                all_available_columns_for_source.append(f"{src_table_obj.name}.{src_col_obj.name}")
                    
                    new_sources = st.multiselect(
                        "Source Columns", 
                        all_available_columns_for_source,
                        default=column_to_edit_obj.source_columns,
                        key=f"edit_src_cols_{table_for_col_edit.name}_{col_index}"
                    )
                    
                    update_col_submit = st.form_submit_button("Update Column")
                    cancel_edit_submit = st.form_submit_button("Cancel")
                    
                    if update_col_submit:
                        column_to_edit_obj.name = new_col_name
                        column_to_edit_obj.data_type = new_col_type
                        column_to_edit_obj.description = new_col_desc
                        column_to_edit_obj.source_columns = new_sources
                        st.session_state.column_to_edit = {} # Clear edit state
                        st.success(f"Column '{column_to_edit_obj.name}' in table '{table_for_col_edit.name}' updated!")
                        update_quality_scores()
                        st.rerun()
                        
                    if cancel_edit_submit:
                        st.session_state.column_to_edit = {} # Clear edit state
                        st.rerun()
            else:
                # Invalid col_index, clear edit state to prevent errors
                st.warning("Column to edit is no longer valid. Please try again.")
                st.session_state.column_to_edit = {}
                st.rerun()
        else:
            # Invalid table_index, clear edit state
            st.warning("Table for column to edit is no longer valid. Please try again.")
            st.session_state.column_to_edit = {}
            st.rerun()

def render_transformations_tab():
    st.header("Transformation Management")
    
    # Create/Edit Transformation Form
    with st.expander("Create/Edit Transformation", expanded=False):
        with st.form("transformation_form"):
            if st.session_state.selected_transformation_index is not None:
                transformation = st.session_state.transformations[st.session_state.selected_transformation_index]
                transformation_name = st.text_input("Transformation Name", value=transformation.name)
                transformation_type = st.selectbox("Transformation Type", ["SQL", "Python", "ETL", "Custom"], 
                                                 index=["SQL", "Python", "ETL", "Custom"].index(transformation.transformation_type)
                                                 if transformation.transformation_type in ["SQL", "Python", "ETL", "Custom"] else 0)
                input_tables = st.multiselect("Input Tables", [table.name for table in st.session_state.tables], default=transformation.input_tables)
                output_tables = st.multiselect("Output Tables", [table.name for table in st.session_state.tables], default=transformation.output_tables)
                transformation_logic = st.text_area("Transformation Logic", value=transformation.logic)
                transformation_description = st.text_area("Transformation Description", value=transformation.description)
                
                # Handle Autosys jobs field for editing
                autosys_jobs_text = "\n".join(transformation.autosys_jobs) if hasattr(transformation, 'autosys_jobs') and transformation.autosys_jobs else ""
                autosys_jobs_input = st.text_area("Autosys Jobs (one per line)", value=autosys_jobs_text, 
                                                help="Enter each Autosys job name on a separate line")
            else:
                transformation_name = st.text_input("Transformation Name")
                transformation_type = st.selectbox("Transformation Type", ["SQL", "Python", "ETL", "Custom"])
                input_tables = st.multiselect("Input Tables", [table.name for table in st.session_state.tables])
                output_tables = st.multiselect("Output Tables", [table.name for table in st.session_state.tables])
                transformation_logic = st.text_area("Transformation Logic")
                transformation_description = st.text_area("Transformation Description")
                autosys_jobs_input = st.text_area("Autosys Jobs (one per line)", 
                                               help="Enter each Autosys job name on a separate line")
            
            submitted = st.form_submit_button("Create/Update Transformation")
            if submitted:
                if not transformation_name or not input_tables or not output_tables:
                    st.error("Transformation Name, Input Tables, and Output Tables are required.")
                else:
                    # Process Autosys jobs
                    autosys_jobs = [job.strip() for job in autosys_jobs_input.split('\n') if job.strip()]
                    
                    if st.session_state.selected_transformation_index is not None:
                        # Update existing transformation
                        st.session_state.transformations[st.session_state.selected_transformation_index].name = transformation_name
                        st.session_state.transformations[st.session_state.selected_transformation_index].transformation_type = transformation_type
                        st.session_state.transformations[st.session_state.selected_transformation_index].input_tables = input_tables
                        st.session_state.transformations[st.session_state.selected_transformation_index].output_tables = output_tables
                        st.session_state.transformations[st.session_state.selected_transformation_index].logic = transformation_logic
                        st.session_state.transformations[st.session_state.selected_transformation_index].description = transformation_description
                        st.session_state.transformations[st.session_state.selected_transformation_index].autosys_jobs = autosys_jobs
                        st.success(f"Transformation '{transformation_name}' updated!")
                    else:
                        # Create new transformation
                        new_transformation = Transformation(
                            transformation_name,
                            transformation_type,
                            input_tables,
                            output_tables,
                            transformation_logic,
                            transformation_description,
                            autosys_jobs=autosys_jobs
                        )
                        st.session_state.transformations.append(new_transformation)
                        st.success(f"Transformation '{transformation_name}' created!")

                    st.session_state.selected_transformation_index = None  # Reset selection
    
    # Display Existing Transformations
    st.subheader("Existing Transformations")
    if st.session_state.transformations:
        for i, transformation in enumerate(st.session_state.transformations):
            col1, col2, col3 = st.columns([0.7, 0.15, 0.15])
            transformation_info = f"- **{transformation.name}**: {transformation.description} (Type: {transformation.transformation_type})"
            col1.write(transformation_info)
            col1.write(f"  - Inputs: {', '.join(transformation.input_tables)}, Outputs: {', '.join(transformation.output_tables)}")
            # Show Autosys jobs if any
            if hasattr(transformation, 'autosys_jobs') and transformation.autosys_jobs:
                col1.write(f"  - Autosys Jobs: {', '.join(transformation.autosys_jobs)}")
            
            if col2.button("Edit", key=f"edit_transformation_{i}"):
                st.session_state.selected_transformation_index = i
                st.rerun()
                
            if col3.button("Delete", key=f"delete_transformation_{i}"):
                if st.session_state.get(f"confirm_delete_trans_{i}", False):
                    st.session_state.transformations.pop(i)
                    st.success(f"Transformation '{transformation.name}' deleted!")
                    st.rerun()
                else:
                    st.session_state[f"confirm_delete_trans_{i}"] = True
                    st.warning(f"Click 'Delete' again to confirm deleting transformation '{transformation.name}'")
            
            # Show code and column mappings
            with st.expander("Show Logic"):
                st.code(transformation.logic, language=transformation.transformation_type.lower() if transformation.transformation_type.lower() in ["sql", "python"] else None)
                
            # Column Mapping management
            with st.expander("Column Mappings"):
                if not hasattr(transformation, 'column_mappings'):
                    transformation.column_mappings = []
                    
                # Form to add new column mapping
                with st.form(f"col_mapping_form_{i}"):
                    # Only show columns from the selected input tables
                    input_options = []
                    for table_name in transformation.input_tables:
                        for table in st.session_state.tables:
                            if table.name == table_name:
                                for column in table.columns:
                                    input_options.append(f"{table.name}.{column.name}")
                    
                    # Only show columns from the selected output tables
                    output_options = []
                    for table_name in transformation.output_tables:
                        for table in st.session_state.tables:
                            if table.name == table_name:
                                for column in table.columns:
                                    output_options.append(f"{table.name}.{column.name}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        source = st.selectbox("Source Column", input_options if input_options else ["No columns available"], key=f"src_map_{i}")
                    with col2:
                        target = st.selectbox("Target Column", output_options if output_options else ["No columns available"], key=f"tgt_map_{i}")
                    
                    transformation_rule = st.text_area("Transformation Rule (optional)", key=f"rule_map_{i}")
                    
                    submitted = st.form_submit_button("Add Mapping")
                    if submitted:
                        if source == "No columns available" or target == "No columns available":
                            st.error("Please select valid source and target columns")
                        else:
                            source_table, source_column = source.split(".")
                            target_table, target_column = target.split(".")
                            
                            mapping = ColumnMapping(
                                source_table=source_table,
                                source_column=source_column,
                                target_table=target_table,
                                target_column=target_column,
                                transformation_rule=transformation_rule
                            )
                            
                            # Add to transformation's column_mappings
                            transformation.column_mappings.append(mapping)
                            
                            # Update source_columns in the target column
                            for table in st.session_state.tables:
                                if table.name == target_table:
                                    for column in table.columns:
                                        if column.name == target_column:
                                            if source not in column.source_columns:
                                                column.source_columns.append(source)
                            
                            st.success("Column mapping added!")
                            update_quality_scores()
                            st.rerun()
                
                # Display existing mappings
                if transformation.column_mappings:
                    st.write("Existing mappings:")
                    for j, mapping in enumerate(transformation.column_mappings):
                        col1, col2 = st.columns([0.8, 0.2])
                        col1.write(f"- {mapping.source_table}.{mapping.source_column} → {mapping.target_table}.{mapping.target_column}")
                        if mapping.transformation_rule:
                            col1.write(f"  Rule: {mapping.transformation_rule}")
                            
                        if col2.button("Delete", key=f"del_mapping_{i}_{j}"):
                            # Remove the mapping
                            transformation.column_mappings.pop(j)
                            
                            # Also remove from source_columns in target column
                            source = f"{mapping.source_table}.{mapping.source_column}"
                            for table in st.session_state.tables:
                                if table.name == mapping.target_table:
                                    for column in table.columns:
                                        if column.name == mapping.target_column:
                                            if source in column.source_columns:
                                                column.source_columns.remove(source)
                            
                            st.success("Mapping deleted!")
                            update_quality_scores()
                            st.rerun()
                else:
                    st.write("No column mappings defined.")
    else:
        st.info("No transformations defined yet. Click 'Create/Edit Transformation' to add one, or use 'Generate Sample Data' in the sidebar.")

def render_lineage_graph_tab():
    st.header("Data Lineage Graph")
    
    if st.session_state.tables and st.session_state.transformations:
        # Graph export options
        st.sidebar.markdown("---")
        with st.sidebar.expander("Export Graph", expanded=False):
            export_format = st.selectbox("Export Format", ["HTML", "PNG", "SVG"])
            export_name = st.text_input("File Name", "lineage_graph")
            if st.button("Export Graph"):
                try:
                    if export_format == "HTML":
                        export_path = f"exports/{export_name}.html"
                        os.makedirs("exports", exist_ok=True)
                        graph = create_lineage_graph(
                            st.session_state.tables,
                            st.session_state.transformations,
                            st.session_state.get("include_columns", False),
                            st.session_state.get("focus_entity", None)
                        )
                        net = Network(height="750px", width="100%")
                        net.from_nx(graph)
                        net.save_graph(export_path)
                        st.success(f"Graph exported as HTML: {export_path}")
                        
                    elif export_format in ["PNG", "SVG"]:
                        from selenium import webdriver
                        from selenium.webdriver.chrome.options import Options
                        import time
                        
                        # Create temp HTML first
                        temp_html = "temp_graph.html"
                        graph = create_lineage_graph(
                            st.session_state.tables,
                            st.session_state.transformations,
                            st.session_state.get("include_columns", False),
                            st.session_state.get("focus_entity", None)
                        )
                        net = Network(height="750px", width="100%")
                        net.from_nx(graph)
                        net.save_graph(temp_html)
                        
                        # Setup Chrome options
                        chrome_options = Options()
                        chrome_options.add_argument("--headless")
                        chrome_options.add_argument("--no-sandbox")
                        chrome_options.add_argument("--window-size=1920,1080")
                        
                        # Create exports directory
                        os.makedirs("exports", exist_ok=True)
                        
                        # Take screenshot
                        driver = webdriver.Chrome(options=chrome_options)
                        driver.get(f"file://{os.path.abspath(temp_html)}")
                        time.sleep(2)  # Wait for graph to render
                        
                        export_path = f"exports/{export_name}.{export_format.lower()}"
                        driver.save_screenshot(export_path) if export_format == "PNG" else driver.get_screenshot_as_file(export_path)
                        
                        driver.quit()
                        os.remove(temp_html)
                        st.success(f"Graph exported as {export_format}: {export_path}")
                        
                except Exception as e:
                    st.error(f"Error exporting graph: {str(e)}")
                    if os.path.exists("temp_graph.html"):
                        os.remove("temp_graph.html")

        with st.container():
            col1, col2 = st.columns([2, 3])
            
            with col1:
                with st.container():
                    st.markdown("### Graph Settings")
                    with st.expander("Layout Options", expanded=True):
                        graph_layout = st.selectbox("Layout Style", 
                                                ["hierarchical", "circular", "force"], 
                                                index=0)
                        physics_enabled = st.checkbox("Enable Physics Simulation", value=True)
                        
                        if graph_layout == "hierarchical":
                            direction = st.selectbox("Direction", ["LR", "RL", "UD", "DU"], 
                                                index=0, 
                                                help="LR=Left to Right, RL=Right to Left, UD=Up to Down, DU=Down to Up")
                        
                        node_spacing = st.slider("Node Spacing", 50, 200, 100)
                        
                    with st.expander("Visual Options", expanded=True):
                        include_columns = st.checkbox("Show Column-level Lineage", value=False)
                        theme = st.selectbox("Color Theme", ["light", "dark"], index=0)
                        smooth_edges = st.checkbox("Smooth Edges", value=True)
                        
                    with st.expander("Focus Options", expanded=True):
                        # Add entity focus for filtering
                        focus_options = ["Show All"]
                        for table in st.session_state.tables:
                            focus_options.append(table.name)
                            if include_columns:
                                for column in table.columns:
                                    focus_options.append(f"{table.name}.{column.name}")
                                    
                        focus_entity = st.selectbox("Focus on Entity", focus_options)
                        focus_entity = None if focus_entity == "Show All" else focus_entity
            
            with col2:
                st.markdown("### Visualization")
                with st.container():
                    graph = create_lineage_graph(
                        st.session_state.tables, 
                        st.session_state.transformations, 
                        include_columns, 
                        focus_entity
                    )
                    
                    if len(graph.nodes) > 0:
                        # Enhanced graph options
                        graph_options = {
                            "layout": {
                                "hierarchical": {
                                    "enabled": graph_layout == "hierarchical",
                                    "direction": direction if graph_layout == "hierarchical" else "LR",
                                    "sortMethod": "directed",
                                    "nodeSpacing": node_spacing,
                                    "levelSeparation": 150
                                }
                            },
                            "edges": {
                                "arrows": "to",
                                "smooth": {
                                    "enabled": smooth_edges,
                                    "type": "cubicBezier",
                                    "roundness": 0.5
                                }
                            },
                            "physics": {
                                "enabled": physics_enabled,
                                "solver": "hierarchicalRepulsion" if graph_layout == "hierarchical" else "forceAtlas2Based",
                                "hierarchicalRepulsion": {
                                    "centralGravity": 0.0,
                                    "springLength": 150,
                                    "springConstant": 0.01,
                                    "nodeDistance": node_spacing
                                },
                                "stabilization": {
                                    "enabled": True,
                                    "iterations": 100,
                                    "updateInterval": 50
                                }
                            },
                            "nodes": {
                                "shape": "dot",
                                "size": 20,
                                "font": {
                                    "size": 14,
                                    "color": "#ffffff" if theme == "dark" else "#000000"
                                }
                            }
                        }
                        
                        #st.markdown('<div class="graph-container">', unsafe_allow_html=True)
                        display_graph(graph, physics=physics_enabled, layout=graph_layout, theme=theme, options=graph_options)
                        #st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.warning("No nodes to display in the graph. Check your filter settings or add more tables/transformations.")
                        
                # Add legend
                with st.expander("Graph Legend", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("🟩 **Tables**")
                    with col2:
                        st.markdown("🟦 **Columns**")
                    with col3:
                        st.markdown("🟨 **Transformations**")
                
                # Add database type legend
                with st.expander("Database Type Colors", expanded=False):
                    st.markdown("**Table Database Types:**")
                    
                    # Create columns for better organization
                    legend_cols = st.columns(3)
                    db_types = list(DATABASE_TYPE_COLORS.keys())
                    
                    for i, db_type in enumerate(db_types):
                        color = DATABASE_TYPE_COLORS[db_type]
                        col_index = i % 3
                        with legend_cols[col_index]:
                            st.markdown(f'<div style="display: flex; align-items: center; margin: 2px 0;"><div style="width: 12px; height: 12px; background-color: {color}; margin-right: 8px; border-radius: 2px;"></div><span>{db_type}</span></div>', 
                                       unsafe_allow_html=True)
                
                # View management
                with st.expander("Manage Views", expanded=False):
                    view_name = st.text_input("View Name")
                    if st.button("Save View"):
                        if view_name:
                            view_settings = {
                                "graph_layout": graph_layout,
                                "physics_enabled": physics_enabled,
                                "direction": direction if graph_layout == "hierarchical" else None,
                                "node_spacing": node_spacing,
                                "include_columns": include_columns,
                                "theme": theme,
                                "smooth_edges": smooth_edges,
                                "focus_entity": focus_entity
                            }
                            st.session_state.saved_views.append({"name": view_name, "settings": view_settings})
                            st.success(f"View '{view_name}' saved!")
                        else:
                            st.error("View name cannot be empty.")
                    
                    if st.session_state.saved_views:
                        selected_view = st.selectbox("Load View", ["Select a view"] + [view["name"] for view in st.session_state.saved_views])
                        if selected_view != "Select a view":
                            for view in st.session_state.saved_views:
                                if view["name"] == selected_view:
                                    view_settings = view["settings"]
                                    graph_layout = view_settings["graph_layout"]
                                    physics_enabled = view_settings["physics_enabled"]
                                    direction = view_settings["direction"]
                                    node_spacing = view_settings["node_spacing"]
                                    include_columns = view_settings["include_columns"]
                                    theme = view_settings["theme"]
                                    smooth_edges = view_settings["smooth_edges"]
                                    focus_entity = view_settings["focus_entity"]
                                    st.success(f"View '{selected_view}' loaded!")
                                    st.rerun()
    else:
        st.info("Define tables and transformations to see the lineage graph. Use 'Generate Sample Data' in the sidebar for a quick demo.")

def render_import_export_tab():
    st.header("Import / Export Lineage Data")
    
    import_export_mode = st.radio("Select Action:", ["Import", "Export"])
    
    if import_export_mode == "Export":
        st.subheader("Export Lineage Data")
        
        if not st.session_state.tables:
            st.warning("No data to export. Add some tables and transformations first.")
            return
            
        export_method = st.radio("Export method:", ["Direct path", "File browser"])
        
        if export_method == "Direct path":
            export_filepath = st.text_input("Export Filepath:", "d:/XCode/data-lineage/lineage_data.json")
            if st.button("Export Data"):
                export_data(st.session_state.tables, st.session_state.transformations, export_filepath)
        else:
            st.write("Select location to save the file:")
            export_path = get_file_path(mode="save")
            if export_path and st.button("Export Data"):
                export_data(st.session_state.tables, st.session_state.transformations, export_path)
    else:  # Import mode
        st.subheader("Import Lineage Data")
        
        st.warning("Importing will replace all current tables and transformations.")
        import_method = st.radio("Import method:", ["Direct path", "File browser"])
        
        if import_method == "Direct path":
            import_filepath = st.text_input("Import Filepath:", "d:/XCode/data-lineage/lineage_data.json")
            if st.button("Import Data") and import_filepath:
                import_data(import_filepath)
        else:
            st.write("Select file to import:")
            import_path = get_file_path(mode="import")
            if import_path and st.button("Import Data"):
                import_data(import_path)

def render_search_tab():
    st.header("Search Lineage")
    
    search_query = st.text_input("Search for tables, columns, or transformations:")
    
    if search_query:
        results = search_lineage(search_query, st.session_state.tables, st.session_state.transformations)
        
        # Tables results
        if results["tables"]:
            st.subheader(f"Tables ({len(results['tables'])})")
            for result in results["tables"]:
                table_type = result.get('table_type', 'Other')
                table_color = DATABASE_TYPE_COLORS.get(table_type, DATABASE_TYPE_COLORS['Other'])
                table_display = f"**{result['name']}** ({result['schema']}) - {table_type}: {result['description']}"
                st.markdown(f'<div style="border-left: 4px solid {table_color}; padding-left: 10px;">{table_display}</div>', 
                           unsafe_allow_html=True)
                if st.button("Show in Graph", key=f"show_graph_{result['name']}_table"):
                    st.session_state.focus_entity = result['name']
                    st.session_state.active_tab = "Lineage Graph"
                    st.rerun()
        
        # Columns results
        if results["columns"]:
            st.subheader(f"Columns ({len(results['columns'])})")
            for result in results["columns"]:
                st.write(f"**{result['name']}** ({result['data_type']}): {result['description']}")
                if st.button("Show in Graph", key=f"show_graph_{result['name']}_column"):
                    st.session_state.focus_entity = result['name']
                    st.session_state.active_tab = "Lineage Graph"
                    st.rerun()
        
        # Transformations results
        if results["transformations"]:
            st.subheader(f"Transformations ({len(results['transformations'])})")
            for result in results["transformations"]:
                st.write(f"**{result['name']}** ({result['type']}): {result['description']}")
                st.write(f"Input: {', '.join(result['input_tables'])} → Output: {', '.join(result['output_tables'])}")
                if st.button("Show in Graph", key=f"show_graph_{result['name']}_transformation"):
                    st.session_state.focus_entity = None  # Show all for transformations
                    st.session_state.active_tab = "Lineage Graph"
                    st.rerun()
        
        # No results
        if not results["tables"] and not results["columns"] and not results["transformations"]:
            st.info("No results found.")
    else:
        st.info("Enter a search term to find tables, columns, or transformations.")

# Execute the main function
if __name__ == "__main__":
    main()