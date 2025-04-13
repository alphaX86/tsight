# TraceSight - Data Lineage Visualization Tool

A powerful and interactive data lineage visualization tool that helps you understand and manage data relationships, transformations, and dependencies in your data ecosystem.

## Features

- 📊 Interactive Data Lineage Graph
  - Column-level and table-level lineage visualization
  - Multiple layout options (hierarchical, circular, force-directed)
  - Custom themes and visualization settings
  - Focus mode for specific entities
  - Save and manage multiple views

- 📝 Comprehensive Data Management
  - Table and column management
  - Transformation tracking
  - Column-level mapping
  - Quality scoring
  - Rich metadata support

- 🔄 Import/Export Capabilities
  - JSON data import/export
  - Graph export in multiple formats (HTML, PNG, SVG)
  - View management system

- 🔍 Search and Navigation
  - Full-text search across tables, columns, and transformations
  - Quick navigation to entities
  - Detailed entity information

## Getting Started

### Prerequisites

- Python 3.7+
- Streamlit
- NetworkX
- PyVis
- Chrome/Chromium (for PNG/SVG export)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/tracesight.git
cd tracesight
```

2. Install dependencies:
```bash
pip install streamlit networkx pyvis selenium
```

### Running the Application

1. Start the Streamlit server:
```bash
streamlit run lin.py
```

2. Open your browser and navigate to the provided URL (typically http://localhost:8501)

## Project Structure

- `lineage.py`: Main application file
- `exports/`: Directory for exported graphs
- `data/`: Directory for saved lineage data
