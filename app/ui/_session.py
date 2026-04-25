import os
import streamlit as st
from app.db import connect


@st.cache_resource
def get_conn():
    return connect(os.environ.get("DB_PATH", "./data/accounting.db"))
