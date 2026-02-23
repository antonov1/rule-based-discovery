import pm4py
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

def extract_rules_from_data(data: pd.DataFrame, case_id_col: str = 'case:concept:name', activity_col: str = 'concept:name'):
    # Convert the DataFrame to an event log
    cases = data[case_id_col].unique()
    traces = []
    for case in cases:
        case_data = data[data[case_id_col] == case].sort_values(by='time:timestamp')
        trace = case_data[activity_col].tolist()
        traces.append(trace)
    

def check_start_end(traces):
    start_activities = set(trace[0] for trace in traces if trace)
    end_activities = set(trace[-1] for trace in traces if trace)
    # Check their support and confidence
    
def rule_mining(traces, min_support: float = 0.5, 
                min_confidence: float = 0.7, 
                rule_size: int = 2):
    te = TransactionEncoder()
    te_ary = te.fit(traces).transform(traces)
    df = pd.DataFrame(te_ary, columns=te.columns_)
    frequent_itemsets = apriori(df, min_support=min_support, use_colnames=True)
    frequent_itemsets['length'] = frequent_itemsets['itemsets'].apply(lambda x: len(x))
    frequent_itemsets = frequent_itemsets[frequent_itemsets['length'] <= rule_size]
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_confidence)
    rules = rules[['antecedents', 'consequents', 'support', 'confidence', 'lift']]
    return rules

def transform_associative_rules_to_declare(rules):
    declare_rules = []
# Example usage
if __name__ == "__main__":
    dataset = [['A', 'B', 'C', 'D'], ['E', 'F', 'G'], ['A', 'C', 'E'], ['B', 'D', 'F']]
    rules = rule_mining(dataset, min_support=0.5, min_confidence=0.7, rule_size=2)
    print(rules)