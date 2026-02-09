import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Configuration de la page
st.set_page_config(
    page_title="💰 Finance Tracker",
    page_icon="💰",
    layout="wide"
)

# Titre principal
st.title("💰 Mon Tracker de Finances")
st.markdown("---")

# Initialisation des données en session
if "expenses" not in st.session_state:
    st.session_state.expenses = []

# Sidebar pour ajouter une dépense
with st.sidebar:
    st.header("➕ Ajouter une dépense")
    
    with st.form("expense_form"):
        description = st.text_input("Description")
        amount = st.number_input("Montant ($)", min_value=0.01, step=0.01)
        category = st.selectbox(
            "Catégorie",
            ["🍔 Alimentation", "🚗 Transport", "🏠 Logement", "🎬 Loisirs", "🛒 Shopping", "📱 Autres"]
        )
        date = st.date_input("Date", datetime.now())
        
        submitted = st.form_submit_button("Ajouter", use_container_width=True)
        
        if submitted and description:
            st.session_state.expenses.append({
                "Description": description,
                "Montant": amount,
                "Catégorie": category,
                "Date": date.strftime("%Y-%m-%d")
            })
            st.success("Dépense ajoutée !")

# Contenu principal
if st.session_state.expenses:
    df = pd.DataFrame(st.session_state.expenses)
    
    # Métriques
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💵 Total des dépenses", f"${df['Montant'].sum():.2f}")
    with col2:
        st.metric("📊 Nombre de transactions", len(df))
    with col3:
        st.metric("📈 Moyenne par transaction", f"${df['Montant'].mean():.2f}")
    
    st.markdown("---")
    
    # Graphiques
    col_chart, col_table = st.columns(2)
    
    with col_chart:
        st.subheader("📊 Dépenses par catégorie")
        fig = px.pie(df, values="Montant", names="Catégorie", hole=0.4)
        fig.update_layout(showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
    
    with col_table:
        st.subheader("📋 Historique des dépenses")
        
        # Afficher chaque dépense avec un bouton de suppression
        for i, expense in enumerate(st.session_state.expenses):
            col_info, col_delete = st.columns([4, 1])
            with col_info:
                st.write(f"**{expense['Description']}** - ${expense['Montant']:.2f} ({expense['Catégorie']}) - {expense['Date']}")
            with col_delete:
                if st.button("🗑️", key=f"delete_{i}", help="Supprimer cette dépense"):
                    st.session_state.expenses.pop(i)
                    st.rerun()
    
    st.markdown("---")
    
    # Bouton pour réinitialiser toutes les dépenses
    if st.button("🗑️ Effacer toutes les dépenses", type="secondary"):
        st.session_state.expenses = []
        st.rerun()
else:
    st.info("👈 Commencez par ajouter une dépense dans la barre latérale !")
    
    # Afficher un exemple
    st.markdown("### 🎯 Fonctionnalités")
    st.markdown("""
    - ➕ **Ajouter des dépenses** avec description, montant et catégorie
    - 📊 **Visualiser** vos dépenses avec un graphique interactif
    - 📋 **Consulter** l'historique de vos transactions
    - 📈 **Suivre** vos statistiques en temps réel
    """)
