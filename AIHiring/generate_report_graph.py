import matplotlib.pyplot as plt
import numpy as np
import os

def generate_hiring_report_graph():
    # Professional styling for a report
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Data based on "10 out of 5 hired" (50% ratio)
    hiring_methods = ['Manual Interviews', 'Rishi AI Platform']
    interviewed = [10, 200]
    hired = [5, 100] # 50% conversion
    
    x = np.arange(len(hiring_methods))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 7), dpi=150)
    
    # Create grouped bars
    rects1 = ax.bar(x - width/2, interviewed, width, label='Total Interviewed', color='#3498db', alpha=0.9)
    rects2 = ax.bar(x + width/2, hired, width, label='Hired / Shortlisted (50%)', color='#2ecc71', alpha=0.9)
    
    # Labels and Titles
    ax.set_title('Hiring Report: Recruitment Scaling & Conversion', fontsize=18, fontweight='bold', pad=25)
    ax.set_ylabel('Number of Employees / Candidates', fontsize=13)
    ax.set_xticks(x)
    ax.set_xticklabels(hiring_methods, fontsize=14, fontweight='bold')
    ax.legend(fontsize=12, loc='upper left', frameon=True)
    
    # Annotate bars with values
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{int(height)}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 5),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=12, fontweight='bold')

    autolabel(rects1)
    autolabel(rects2)
    
    # Add a text box with the key insight
    insight_text = (
        "Key Insights:\n"
        "• Manual: 50% shortlisting (5/10)\n"
        "• Platform: 50% shortlisting (100/200)\n"
        "• Scale: 20x higher volume with AI"
    )
    plt.text(1.2, 110, insight_text, fontsize=12, bbox=dict(facecolor='white', alpha=0.8, edgecolor='#ccc'))
    
    plt.tight_layout()
    
    # Ensure directory exists
    output_dir = 'static/images'
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'hiring_report.png')
    plt.savefig(output_path, bbox_inches='tight')
    print(f"✅ Hiring report graph saved: {output_path}")

if __name__ == "__main__":
    generate_hiring_report_graph()
