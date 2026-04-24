"""
Hamburg Building Permit Data - Visualization Script

This script creates comprehensive visualizations for the building permit dataset.
Run after installing visualization libraries: uv add matplotlib seaborn
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Import project functions
from src.data_analysis import print_basic_info

def setup_style():
    """Set up matplotlib style for better-looking plots."""
    plt.style.use('seaborn-v0_8-darkgrid')
    plt.rcParams['figure.figsize'] = (10, 6)
    plt.rcParams['font.size'] = 10
    plt.rcParams['axes.labelsize'] = 11
    plt.rcParams['axes.titlesize'] = 12
    plt.rcParams['xtick.labelsize'] = 9
    plt.rcParams['ytick.labelsize'] = 9
    plt.rcParams['legend.fontsize'] = 9


def plot_decision_time_distribution(df, save_path=None):
    """Plot distribution of decision times."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Histogram
    ax1.hist(df['Time for Decision (months)'], bins=20, edgecolor='black', alpha=0.7)
    mean_time = df['Time for Decision (months)'].mean()
    median_time = df['Time for Decision (months)'].median()
    ax1.axvline(mean_time, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_time:.2f}')
    ax1.axvline(median_time, color='green', linestyle='--', linewidth=2, label=f'Median: {median_time:.2f}')
    ax1.set_xlabel('Time for Decision (months)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Distribution of Permit Decision Times')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Box plot
    ax2.boxplot(df['Time for Decision (months)'], vert=True)
    ax2.set_ylabel('Time for Decision (months)')
    ax2.set_title('Decision Time Box Plot')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_issuing_authority_analysis(df, save_path=None):
    """Analyze permits by issuing authority."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Permit count by authority
    authority_counts = df['Issuing Authority'].value_counts()
    colors = plt.cm.Set3(range(len(authority_counts)))
    
    ax1.barh(range(len(authority_counts)), authority_counts.values, color=colors)
    ax1.set_yticks(range(len(authority_counts)))
    ax1.set_yticklabels(authority_counts.index, fontsize=9)
    ax1.set_xlabel('Number of Permits')
    ax1.set_title('Permits by Issuing Authority')
    ax1.grid(True, axis='x', alpha=0.3)
    
    # Add value labels
    for i, v in enumerate(authority_counts.values):
        ax1.text(v + 0.5, i, str(v), va='center')
    
    # Pie chart
    ax2.pie(authority_counts.values, labels=authority_counts.index, autopct='%1.1f%%',
            startangle=90, colors=colors)
    ax2.set_title('Authority Distribution (%)')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_decision_time_by_authority(df, save_path=None):
    """Compare decision times across authorities."""
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Prepare data for box plot
    authorities = df['Issuing Authority'].unique()
    data_to_plot = [df[df['Issuing Authority'] == auth]['Time for Decision (months)'].dropna() 
                    for auth in authorities]
    
    bp = ax.boxplot(data_to_plot, labels=authorities, patch_artist=True)
    
    # Color the boxes
    colors = plt.cm.Set3(range(len(authorities)))
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    
    ax.set_ylabel('Time for Decision (months)')
    ax.set_title('Decision Time by Issuing Authority')
    ax.grid(True, axis='y', alpha=0.3)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_district_analysis(df, save_path=None):
    """Analyze permits by district."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    district_counts = df['District'].value_counts().head(10)
    
    bars = ax.barh(range(len(district_counts)), district_counts.values, 
                   color=plt.cm.viridis(np.linspace(0.3, 0.9, len(district_counts))))
    ax.set_yticks(range(len(district_counts)))
    ax.set_yticklabels(district_counts.index)
    ax.set_xlabel('Number of Permits')
    ax.set_title('Top 10 Districts by Number of Permits')
    ax.grid(True, axis='x', alpha=0.3)
    
    # Add value labels
    for i, v in enumerate(district_counts.values):
        ax.text(v + 0.2, i, str(v), va='center')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_building_characteristics(df, save_path=None):
    """Plot building stories and exemptions."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Number of full stories
    story_counts = df['Number of Full Stories'].value_counts().sort_index()
    ax1.bar(story_counts.index, story_counts.values, color='steelblue', edgecolor='black')
    ax1.set_xlabel('Number of Full Stories')
    ax1.set_ylabel('Count')
    ax1.set_title('Distribution of Building Stories')
    ax1.grid(True, axis='y', alpha=0.3)
    for i, v in zip(story_counts.index, story_counts.values):
        ax1.text(i, v + 1, str(v), ha='center')
    
    # 2. Number of exemptions
    exemption_counts = df['Number of Exemptions'].value_counts().sort_index()
    ax2.bar(exemption_counts.index, exemption_counts.values, color='coral', edgecolor='black')
    ax2.set_xlabel('Number of Exemptions')
    ax2.set_ylabel('Count')
    ax2.set_title('Distribution of Exemptions')
    ax2.grid(True, axis='y', alpha=0.3)
    for i, v in zip(exemption_counts.index, exemption_counts.values):
        ax2.text(i, v + 1, str(v), ha='center')
    
    # 3. Building use distribution
    use_data = {
        'Residential': df['Residential'].sum(),
        'Commercial': df['Commercial'].sum(),
        'Other': df['Other'].sum()
    }
    colors_pie = ['#66b3ff', '#ff9999', '#99ff99']
    ax3.pie(use_data.values(), labels=use_data.keys(), autopct='%1.1f%%',
            startangle=90, colors=colors_pie)
    ax3.set_title('Building Use Distribution')
    
    # 4. Number of documents distribution
    ax4.hist(df['Number of Documents'].dropna(), bins=15, color='mediumpurple', 
             edgecolor='black', alpha=0.7)
    mean_docs = df['Number of Documents'].mean()
    ax4.axvline(mean_docs, color='red', linestyle='--', linewidth=2, 
                label=f'Mean: {mean_docs:.1f}')
    ax4.set_xlabel('Number of Documents')
    ax4.set_ylabel('Frequency')
    ax4.set_title('Distribution of Document Counts')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_complexity_analysis(df, save_path=None):
    """Analyze relationship between documents, exemptions, and decision time."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Documents vs Decision Time
    mask1 = df['Number of Documents'].notna() & df['Time for Decision (months)'].notna()
    x1 = df.loc[mask1, 'Number of Documents']
    y1 = df.loc[mask1, 'Time for Decision (months)']
    
    ax1.scatter(x1, y1, alpha=0.6, s=50, color='steelblue')
    
    # Add trend line
    z1 = np.polyfit(x1, y1, 1)
    p1 = np.poly1d(z1)
    ax1.plot(x1, p1(x1), "r--", linewidth=2, label=f'Trend: y={z1[0]:.3f}x+{z1[1]:.2f}')
    
    # Calculate correlation
    corr1 = x1.corr(y1)
    ax1.text(0.05, 0.95, f'Correlation: {corr1:.3f}', 
             transform=ax1.transAxes, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    ax1.set_xlabel('Number of Documents')
    ax1.set_ylabel('Time for Decision (months)')
    ax1.set_title('Documents vs Decision Time')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Exemptions vs Decision Time
    x2 = df['Number of Exemptions']
    y2 = df['Time for Decision (months)']
    
    ax2.scatter(x2, y2, alpha=0.6, s=50, color='coral')
    
    # Add trend line
    z2 = np.polyfit(x2, y2, 1)
    p2 = np.poly1d(z2)
    ax2.plot(sorted(x2), p2(sorted(x2)), "r--", linewidth=2, 
             label=f'Trend: y={z2[0]:.3f}x+{z2[1]:.2f}')
    
    # Calculate correlation
    corr2 = x2.corr(y2)
    ax2.text(0.05, 0.95, f'Correlation: {corr2:.3f}', 
             transform=ax2.transAxes, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    ax2.set_xlabel('Number of Exemptions')
    ax2.set_ylabel('Time for Decision (months)')
    ax2.set_title('Exemptions vs Decision Time')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_building_function_analysis(df, save_path=None):
    """Analyze building functions."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    function_counts = df['building function + requirements'].value_counts().head(10)
    
    bars = ax.barh(range(len(function_counts)), function_counts.values,
                   color=plt.cm.Paired(np.linspace(0, 1, len(function_counts))))
    ax.set_yticks(range(len(function_counts)))
    ax.set_yticklabels(function_counts.index)
    ax.set_xlabel('Number of Permits')
    ax.set_title('Top 10 Building Functions/Requirements')
    ax.grid(True, axis='x', alpha=0.3)
    
    # Add value labels
    for i, v in enumerate(function_counts.values):
        ax.text(v + 0.5, i, str(v), va='center')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def plot_exceeded_metrics(df, save_path=None):
    """Plot exceeded building boundary and floor area ratio."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    
    # Building Boundary exceedances
    boundary_data = df['Exceeded Building Boundary (meters)'].dropna()
    if len(boundary_data) > 0:
        ax1.hist(boundary_data, bins=15, color='salmon', edgecolor='black', alpha=0.7)
        ax1.set_xlabel('Exceeded Building Boundary (meters)')
        ax1.set_ylabel('Frequency')
        ax1.set_title(f'Building Boundary Exceedances (n={len(boundary_data)})')
        ax1.grid(True, alpha=0.3)
    else:
        ax1.text(0.5, 0.5, 'No data available', ha='center', va='center', 
                transform=ax1.transAxes)
        ax1.set_title('Building Boundary Exceedances')
    
    # Floor Area Ratio exceedances
    far_data = df['Exceeded Floor Area Ratio'].dropna()
    if len(far_data) > 0:
        ax2.hist(far_data, bins=10, color='lightgreen', edgecolor='black', alpha=0.7)
        ax2.set_xlabel('Exceeded Floor Area Ratio')
        ax2.set_ylabel('Frequency')
        ax2.set_title(f'Floor Area Ratio Exceedances (n={len(far_data)})')
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, 'No data available', ha='center', va='center',
                transform=ax2.transAxes)
        ax2.set_title('Floor Area Ratio Exceedances')
    
    # Scatter plot of both metrics
    if len(boundary_data) > 0 and len(far_data) > 0:
        merged = df[['Exceeded Building Boundary (meters)', 'Exceeded Floor Area Ratio']].dropna()
        if len(merged) > 0:
            ax3.scatter(merged['Exceeded Building Boundary (meters)'], 
                       merged['Exceeded Floor Area Ratio'],
                       alpha=0.6, s=50, color='purple')
            ax3.set_xlabel('Exceeded Building Boundary (meters)')
            ax3.set_ylabel('Exceeded Floor Area Ratio')
            ax3.set_title('Building Boundary vs Floor Area Ratio Exceedances')
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(0.5, 0.5, 'No overlapping data', ha='center', va='center',
                    transform=ax3.transAxes)
    else:
        ax3.text(0.5, 0.5, 'Insufficient data', ha='center', va='center',
                transform=ax3.transAxes)
        ax3.set_title('Boundary vs Floor Area Exceedances')
    
    # Data availability chart
    data_availability = {
        'Building Boundary': len(df['Exceeded Building Boundary (meters)'].dropna()),
        'Floor Area Ratio': len(df['Exceeded Floor Area Ratio'].dropna()),
        'Both Metrics': len(df[['Exceeded Building Boundary (meters)', 
                                 'Exceeded Floor Area Ratio']].dropna())
    }
    ax4.bar(data_availability.keys(), data_availability.values(), 
           color=['salmon', 'lightgreen', 'purple'], edgecolor='black')
    ax4.set_ylabel('Number of Permits')
    ax4.set_title('Data Availability for Exceedance Metrics')
    ax4.grid(True, axis='y', alpha=0.3)
    for i, (k, v) in enumerate(data_availability.items()):
        ax4.text(i, v + 1, str(v), ha='center')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def create_comprehensive_dashboard(df, save_path=None):
    """Create a comprehensive dashboard with all key metrics."""
    fig = plt.figure(figsize=(20, 14))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # Row 1, Col 1: Decision time distribution
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.hist(df['Time for Decision (months)'], bins=15, edgecolor='black', alpha=0.7)
    mean_time = df['Time for Decision (months)'].mean()
    ax1.axvline(mean_time, color='red', linestyle='--', label=f'Mean: {mean_time:.2f}')
    ax1.set_xlabel('Time (months)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Decision Time Distribution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Row 1, Col 2: Authority distribution
    ax2 = fig.add_subplot(gs[0, 1])
    authority_counts = df['Issuing Authority'].value_counts()
    ax2.pie(authority_counts.values, labels=authority_counts.index, autopct='%1.0f%%',
            textprops={'fontsize': 8})
    ax2.set_title('Permits by Authority')
    
    # Row 1, Col 3: District top 5
    ax3 = fig.add_subplot(gs[0, 2])
    district_counts = df['District'].value_counts().head(5)
    ax3.barh(range(len(district_counts)), district_counts.values, color='steelblue')
    ax3.set_yticks(range(len(district_counts)))
    ax3.set_yticklabels(district_counts.index, fontsize=9)
    ax3.set_xlabel('Count')
    ax3.set_title('Top 5 Districts')
    ax3.grid(True, axis='x', alpha=0.3)
    
    # Row 2, Col 1: Stories distribution
    ax4 = fig.add_subplot(gs[1, 0])
    story_counts = df['Number of Full Stories'].value_counts().sort_index()
    ax4.bar(story_counts.index, story_counts.values, color='coral', edgecolor='black')
    ax4.set_xlabel('Stories')
    ax4.set_ylabel('Count')
    ax4.set_title('Building Stories')
    ax4.grid(True, axis='y', alpha=0.3)
    
    # Row 2, Col 2: Exemptions distribution
    ax5 = fig.add_subplot(gs[1, 1])
    exemption_counts = df['Number of Exemptions'].value_counts().sort_index()
    ax5.bar(exemption_counts.index, exemption_counts.values, color='mediumpurple', 
            edgecolor='black')
    ax5.set_xlabel('Exemptions')
    ax5.set_ylabel('Count')
    ax5.set_title('Number of Exemptions')
    ax5.grid(True, axis='y', alpha=0.3)
    
    # Row 2, Col 3: Documents vs Time scatter
    ax6 = fig.add_subplot(gs[1, 2])
    mask = df['Number of Documents'].notna() & df['Time for Decision (months)'].notna()
    ax6.scatter(df.loc[mask, 'Number of Documents'], 
               df.loc[mask, 'Time for Decision (months)'],
               alpha=0.6, s=30)
    ax6.set_xlabel('Documents')
    ax6.set_ylabel('Time (months)')
    ax6.set_title('Documents vs Decision Time')
    ax6.grid(True, alpha=0.3)
    
    # Row 3, Col 1-3: Building function distribution
    ax7 = fig.add_subplot(gs[2, :])
    function_counts = df['building function + requirements'].value_counts().head(8)
    ax7.barh(range(len(function_counts)), function_counts.values,
            color=plt.cm.Set3(range(len(function_counts))))
    ax7.set_yticks(range(len(function_counts)))
    ax7.set_yticklabels(function_counts.index)
    ax7.set_xlabel('Number of Permits')
    ax7.set_title('Top 8 Building Functions')
    ax7.grid(True, axis='x', alpha=0.3)
    
    fig.suptitle('Hamburg Building Permit Analysis - Comprehensive Dashboard', 
                fontsize=16, fontweight='bold', y=0.995)
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()


def main():
    """Main function to run all visualizations."""
    # Setup
    setup_style()
    
    # Define paths
    data_dir = Path(__file__).parent / "data"
    raw_file = data_dir / "raw" / "hamburg_permits.xlsx"  # Change to your filename
    output_dir = data_dir / "processed" / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load data
    print("Loading data...")
    if not raw_file.exists():
        print(f"Error: File not found: {raw_file}")
        print("Please update the filename in this script or place your file in data/raw/")
        return
    
    df = pd.read_excel(raw_file)
    print(f"Loaded {len(df)} permits\n")
    
    # Print basic info
    print_basic_info(df)
    
    # Create visualizations
    print("\n" + "="*60)
    print("CREATING VISUALIZATIONS")
    print("="*60)
    
    print("\n1. Decision time analysis...")
    plot_decision_time_distribution(df, output_dir / "01_decision_time.png")
    
    print("2. Issuing authority analysis...")
    plot_issuing_authority_analysis(df, output_dir / "02_authorities.png")
    
    print("3. Decision time by authority...")
    plot_decision_time_by_authority(df, output_dir / "03_time_by_authority.png")
    
    print("4. District analysis...")
    plot_district_analysis(df, output_dir / "04_districts.png")
    
    print("5. Building characteristics...")
    plot_building_characteristics(df, output_dir / "05_building_chars.png")
    
    print("6. Complexity analysis...")
    plot_complexity_analysis(df, output_dir / "06_complexity.png")
    
    print("7. Building function analysis...")
    plot_building_function_analysis(df, output_dir / "07_functions.png")
    
    print("8. Exceeded metrics analysis...")
    plot_exceeded_metrics(df, output_dir / "08_exceeded_metrics.png")
    
    print("9. Creating comprehensive dashboard...")
    create_comprehensive_dashboard(df, output_dir / "09_dashboard.png")
    
    print("\n" + "="*60)
    print("✅ ALL VISUALIZATIONS COMPLETE!")
    print("="*60)
    print(f"\nVisualizations saved to: {output_dir}")
    print("\nGenerated files:")
    for f in sorted(output_dir.glob("*.png")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
