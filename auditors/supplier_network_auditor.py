# auditors/supplier_network_auditor.py
import pandas as pd
import networkx as nx
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
from collections import defaultdict

class SupplierNetworkAuditor:
    """
    Analyzes supplier relationships across multiple councils to detect
    potential monopolies or coordinated networks.
    """
    
    def __init__(self):
        self.supplier_council_map = defaultdict(set)  # supplier -> set of councils
        self.council_supplier_map = defaultdict(set)  # council -> set of suppliers
        self.supplier_value_map = defaultdict(float)  # supplier -> total value
        self.all_transactions = []
    
    def add_council_data(self, council_name: str, df: pd.DataFrame,
                     supplier_col: str = None, value_col: str = 'amount'):
        """
        Improved version that finds the supplier column if not specified.
        """
        # If supplier column not provided, try to find it
        if supplier_col is None:
            possible_names = ['supplier', 'payee', 'vendor', 'supplier_name']
            for name in possible_names:
                if name in df.columns:
                    supplier_col = name
                    break
            if supplier_col is None:
                raise KeyError(f"Could not find a supplier column in data for {council_name}. Columns: {list(df.columns)}")
        
        print(f"📥 Loading {council_name}: using column '{supplier_col}' for supplier names.")
        
        # ... rest of the existing method code ...
    
    def detect_multi_council_suppliers(self, min_councils: int = 3) -> pd.DataFrame:
        """
        Find suppliers operating in multiple councils.
        Returns DataFrame sorted by reach and total value.
        """
        multi_suppliers = []
        
        for supplier, councils in self.supplier_council_map.items():
            if len(councils) >= min_councils:
                total_value = self.supplier_value_map[supplier]
                avg_per_council = total_value / len(councils)
                
                multi_suppliers.append({
                    'supplier': supplier,
                    'council_count': len(councils),
                    'councils': ', '.join(sorted(councils)),
                    'total_value': total_value,
                    'avg_per_council': avg_per_council,
                    'risk_score': len(councils) * (1 if total_value > 1000000 else 0.5)
                })
        
        result_df = pd.DataFrame(multi_suppliers)
        if not result_df.empty:
            result_df = result_df.sort_values(['council_count', 'total_value'], ascending=False)
        
        return result_df
    
    def detect_potential_cartels(self, min_suppliers: int = 3) -> List[Tuple]:
        """
        Find groups of suppliers that consistently appear together across councils.
        Returns list of (supplier_group, council_count) tuples.
        """
        # Create supplier sets for each council
        council_supplier_sets = {
            council: frozenset(suppliers) 
            for council, suppliers in self.council_supplier_map.items()
        }
        
        # Find common supplier combinations
        combination_counts = defaultdict(int)
        
        for council, supplier_set in council_supplier_sets.items():
            if len(supplier_set) >= min_suppliers:
                # Convert to sorted tuple for hashing
                supplier_tuple = tuple(sorted(supplier_set))
                combination_counts[supplier_tuple] += 1
        
        # Filter for combinations appearing in multiple councils
        potential_cartels = [
            (list(combo), count)
            for combo, count in combination_counts.items()
            if count >= 2 and len(combo) >= min_suppliers
        ]
        
        return sorted(potential_cartels, key=lambda x: (x[1], len(x[0])), reverse=True)
    
    def generate_network_graph(self, output_path: str = None):
        """
        Create a visualization of the supplier-council network.
        """
        G = nx.Graph()
        
        # Add nodes with attributes
        for supplier, councils in self.supplier_council_map.items():
            if len(councils) >= 2:  # Only show suppliers in multiple councils
                G.add_node(supplier, type='supplier', size=self.supplier_value_map[supplier])
        
        for council in self.council_supplier_map.keys():
            G.add_node(council, type='council', size=len(self.council_supplier_map[council]))
        
        # Add edges
        for supplier, councils in self.supplier_council_map.items():
            if len(councils) >= 2:
                for council in councils:
                    G.add_edge(supplier, council)
        
        # Draw the graph
        plt.figure(figsize=(14, 10))
        
        # Separate node types for coloring
        supplier_nodes = [n for n, attr in G.nodes(data=True) if attr.get('type') == 'supplier']
        council_nodes = [n for n, attr in G.nodes(data=True) if attr.get('type') == 'council']
        
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # Draw suppliers in red, councils in blue
        nx.draw_networkx_nodes(G, pos, nodelist=supplier_nodes, 
                              node_color='red', node_size=300, alpha=0.7)
        nx.draw_networkx_nodes(G, pos, nodelist=council_nodes, 
                              node_color='blue', node_size=500, alpha=0.5)
        
        nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color='gray')
        
        # Labels for suppliers only (to avoid clutter)
        supplier_labels = {n: n[:15] + '...' if len(n) > 15 else n 
                          for n in supplier_nodes}
        nx.draw_networkx_labels(G, pos, labels=supplier_labels, font_size=8)
        
        council_labels = {n: n for n in council_nodes}
        nx.draw_networkx_labels(G, pos, labels=council_labels, font_size=10, font_weight='bold')
        
        plt.title(f"Supplier-Council Network\n({len(supplier_nodes)} suppliers across {len(council_nodes)} councils)")
        plt.axis('off')
        
        if output_path:
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            print(f"💾 Network graph saved to {output_path}")
        
        return G, plt
    
    def generate_report(self) -> Dict:
        """
        Generate a comprehensive network analysis report.
        """
        multi_suppliers = self.detect_multi_council_suppliers(min_councils=2)
        potential_cartels = self.detect_potential_cartels(min_suppliers=3)
        
        return {
            'total_councils': len(self.council_supplier_map),
            'total_suppliers': len(self.supplier_council_map),
            'total_transactions': len(self.all_transactions),
            'total_value': sum(self.supplier_value_map.values()),
            'multi_council_suppliers': multi_suppliers.to_dict('records') if not multi_suppliers.empty else [],
            'top_suppliers_by_value': sorted(
                [(s, v) for s, v in self.supplier_value_map.items()], 
                key=lambda x: x[1], reverse=True
            )[:20],
            'potential_cartels': potential_cartels,
            'councils_most_shared_suppliers': sorted(
                [(c, len(suppliers)) for c, suppliers in self.council_supplier_map.items()],
                key=lambda x: x[1], reverse=True
            )[:10]
        }