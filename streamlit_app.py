import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import date, timedelta

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
st.set_page_config(page_title="StockClaro", layout="wide")

if "user" not in st.session_state: st.session_state.user = None

with st.sidebar:
    st.markdown("## 📦 StockClaro")
    st.caption("Tu inventario claro y sin pérdidas")
    menu = st.radio("Menú", ["Inventario","Caducidad","Entradas/Salidas","Historial de movimientos","Separados","Mi cuenta"], label_visibility="collapsed")
    st.divider()
    if st.session_state.user:
        st.write(f"👤 {st.session_state.user.email}")
        if st.button("Cerrar sesión"):
            st.session_state.user=None; st.rerun()
    else:
        st.write("No has iniciado sesión")
        if st.button("Iniciar sesión"): st.session_state.login_open=True; st.session_state.reg_open=False
        if st.button("Crear cuenta nueva"): st.session_state.reg_open=True; st.session_state.login_open=False
        st.divider()
        if st.button("Iniciar como Administrador"): st.session_state.login_open=True; st.session_state.admin_mode=True

# REGISTRO
if not st.session_state.user and st.session_state.get("reg_open"):
    st.title("📦 Crea tu cuenta")
    st.write("Empieza a controlar tu tienda hoy")
    e=st.text_input("Correo electrónico"); p=st.text_input("Contraseña",type="password"); t=st.text_input("Nombre de tu tienda")
    if st.button("Crear cuenta"):
        try:
            r = supabase.auth.sign_up({"email": e, "password": p})
            # como ya no pide confirmación, entra directo
            res = supabase.auth.sign_in_with_password({"email": e, "password": p})
            supabase.table("profiles").insert({"id": res.user.id, "email": e, "rol": "cliente", "plan": "basico", "activo": True, "tienda": t}).execute()
        
            st.session_state.user = res.user
            st.success(f"¡Bienvenido {t}! Entrando...")
            st.session_state.reg_open = False
            st.rerun()
        except Exception as ex:
                st.error(f"Error: {ex}")
    if st.button("Volver"): st.session_state.reg_open=False; st.rerun()
    st.stop()

# LOGIN
if not st.session_state.user and st.session_state.get("login_open"):
    is_admin=st.session_state.get("admin_mode",False)
    st.title("🔑 Acceso Administrador" if is_admin else "📦 Bienvenido a StockClaro")
    email=st.text_input("Correo electrónico"); pwd=st.text_input("Contraseña",type="password")
    if st.button("Entrar"):
        try:
            res=supabase.auth.sign_in_with_password({"email":email,"password":pwd})
            prof=supabase.table("profiles").select("*").eq("id",res.user.id).single().execute().data
            if is_admin and prof.get("rol")!="superadmin": st.error("No eres administrador")
            else: st.session_state.user=res.user; st.session_state.login_open=False;
        except Exception as ex: st.error(f"Error: {ex}")
    if st.button("Cancelar"): st.session_state.login_open=False; st.session_state.admin_mode=False; st.rerun()
    st.stop()

if not st.session_state.user:
    st.title("📦 StockClaro"); st.info("Inicia sesión o crea tu cuenta desde el menú izquierdo.")
    st.stop()

user = st.session_state.user; uid = user.id
prof = supabase.table("profiles").select("*").eq("id", uid).single().execute().data
rol = prof.get("rol", "cliente") if prof else "cliente"

uid_view = uid
if rol == "superadmin":
    st.sidebar.divider(); st.sidebar.subheader("👑 Admin")
    clientes = supabase.table("profiles").select("*").eq("rol","cliente").execute().data or []
    if clientes:
        sel = st.sidebar.selectbox("Ver cliente", [(c["id"],c["email"]) for c in clientes], format_func=lambda x: x[1])
        uid_view = sel[0]

@st.cache_data(ttl=30)
def get_prods(uid):
    return supabase.table("productos").select("*").eq("user_id", uid).order("nombre").execute().data or []

@st.cache_data(ttl=30)
def get_movs(uid):
    return supabase.table("movimientos").select("*, productos(nombre)").eq("user_id", uid).order("created_at", desc=True).limit(200).execute().data or []
if menu=="Inventario":
    st.title("📦 StockClaro")
    st.header("Inventario")
    prods = get_prods(uid_view) or []
    if not prods:
        st.info("No hay productos. Regístralos en Entradas/Salidas > Entradas")
    else:
        df = pd.DataFrame(prods)
        for c in ["precio_compra", "precio_venta", "precio"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        # Si la columna viene como 'precio', la renombramos a 'precio_venta'
        if "precio_venta" not in df.columns and "precio" in df.columns:
            df = df.rename(columns={"precio": "precio_venta"})

        cols = [c for c in ["sku","nombre","categoria","stock","precio_compra","precio_venta"] if c in df.columns]
        df_show = df[cols] if cols else df
        df_show.index = range(1, len(df_show) + 1)
        st.dataframe(
            df_show,
            use_container_width=True,
            column_config={
                "precio_compra": st.column_config.NumberColumn("Compra", format="$ %.2f"),
                "precio_venta": st.column_config.NumberColumn("Venta", format="$ %.2f"),
            }
        )

        # --- Totales abajo ---
        df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
        total_compra = (df["stock"] * df["precio_compra"]).sum() if "precio_compra" in df.columns else 0
        total_venta = (df["stock"] * df["precio_venta"]).sum() if "precio_venta" in df.columns else 0
        ganancia = total_venta - total_compra
        st.divider()
        c1, c2, c3 = st.columns(3)
    with c1:
        st.write("Total inversión (compra)")
        st.header(f"${total_compra:,.2f}")
    with c2:
        st.write("Total valor venta")
        st.header(f"${total_venta:,.2f}")
    with c3:
        st.write("Potencial de Ganancia")
        st.header(f"${ganancia:,.2f}")
elif menu=="Caducidad":
    st.header("⏳ Caducidad")
    prods = get_prods(uid_view)
    hoy = date.today()
    prox = []
    for p in prods:
        c = p.get("fecha_caducidad")
        if not c: continue
        try:
            fc = date.fromisoformat(str(c)[:10])
            dias = (fc - hoy).days
            if dias <= 30:
                prox.append((fc, dias, p))
        except:
            continue
    prox.sort()
    if not prox:
        st.success("No hay productos por caducar en 30 días")
    else:
        for fc, dias, p in prox:
            color = "🔴" if dias < 0 else "🟡" if dias <= 7 else "🟢"
            st.write(f"{color} **{p['nombre']}** - {fc} ({dias} días) - Stock: {p.get('stock', 0)}")

elif menu=="Entradas/Salidas":
    st.header("Entradas / Salidas")
    tab1, tab2 = st.tabs(["Entradas", "Salidas"])

    @st.cache_data(ttl=30)
    def get_prods(uid):
        try:
            r = supabase.table("productos").select("id, sku, nombre, stock").eq("user_id", uid).order("nombre").execute()
            return r.data or []
        except:
            return []

    prods = get_prods(uid_view)
    prod_dict = {p["nombre"]: p for p in prods if "nombre" in p}

    with tab1:
        st.subheader("Entrada de producto")
        tipo = st.radio("Tipo de entrada", ["Nuevo producto", "Agregar stock"], horizontal=True)

        if tipo == "Nuevo producto":
            with st.form("form_nuevo", clear_on_submit=True):
                sku = st.text_input("SKU")
                nombre = st.text_input("Nombre*")
                stock_ini = st.number_input("Stock inicial", min_value=0, step=1)
                categoria = st.selectbox("Categoría", ["Bebidas", "Botanas", "Abarrotes", "Otros"])
                precio_compra = st.number_input("Precio compra", min_value=0.0, step=1.0)
                precio_venta = st.number_input("Precio venta", min_value=0.0, step=1.0)
                caducidad = st.date_input("Caducidad")
                proveedor = st.text_input("Proveedor")
                guardar = st.form_submit_button("Guardar")

                if guardar:
                    if not nombre:
                        st.error("El Nombre es obligatorio")
                    else:
                        supabase.table("productos").insert({
                            "sku": sku,
                            "nombre": nombre,
                            "stock": int(stock_ini),
                            "categoria": categoria,
                            "precio_compra": float(precio_compra),
                            "precio_venta": float(precio_venta),
                            "caducidad": str(caducidad),
                             "proveedor": proveedor,
                             "user_id": uid_view
                        }).execute()
                        st.cache_data.clear()
                        st.success("Producto guardado")
                        st.rerun()
        else:
            with st.form("form_stock", clear_on_submit=True):
                sel = st.selectbox("Producto", list(prod_dict.keys()) if prod_dict else ["Sin productos"])
                cant = st.number_input("Cantidad a agregar", min_value=1, step=1)
                btn = st.form_submit_button("Agregar stock")
                if btn and prod_dict:
                    p = prod_dict[sel]
                    nuevo_stock = int(p["stock"] or 0) + int(cant)
                    supabase.table("productos").update({"stock": nuevo_stock}).eq("id", p["id"]).eq("user_id", uid_view).execute()
                    supabase.table("movimientos").insert({
                        "producto_id": p["id"],
                        "tipo": "entrada",
                        "cantidad": int(cant),
                        "user_id": uid_view
                    }).execute()
                    st.success(f"Stock actualizado: {nuevo_stock}")
                    st.cache_data.clear()
                    st.rerun()
    with tab2:
        st.subheader("Salida de producto")
        with st.form("form_salida", clear_on_submit=True):
            sel2 = st.selectbox("Producto", list(prod_dict.keys()) if prod_dict else ["Sin productos"], key="sal")
            cant2 = st.number_input("Cantidad a retirar", min_value=1, step=1)
            btn2 = st.form_submit_button("Registrar salida")
            if btn2 and prod_dict:
                p = prod_dict[sel2]
                actual = int(p["stock"] or 0)
                if cant2 > actual:
                    st.error(f"No hay suficiente stock. Actual: {actual}")
                else:
                    supabase.table("productos").update({"stock": actual - int(cant2)}).eq("id", p["id"]).eq("user_id", uid_view).execute()
                    supabase.table("movimientos").insert({
                        "producto_id": p["id"],
                        "tipo": "salida",
                        "cantidad": int(cant2),
                        "user_id": uid_view
                    }).execute()
                    st.success("Salida registrada")
                    st.cache_data.clear()
                    st.rerun()
elif menu=="Separados":
        st.header("Separados")
        st.write("Bloque Separados OK")

elif menu=="Mi cuenta":
        st.header("Mi cuenta")
        st.write(f"**{user.email}**")
        st.write(f"Rol: {rol}")
        try:
            r=supabase.table("profiles").select("tienda").eq("id",user.id).execute()
            tienda_actual=r.data[0].get("tienda","") if r.data else ""
        except:
            tienda_actual=""
        tienda=st.text_input("Nombre de la tienda", value=tienda_actual)
        if st.button("Guardar"):
            try:
                supabase.table("profiles").update({"tienda":tienda}).eq("id",user.id).execute()
                st.success("Tienda guardada")
            except Exception as e:
                st.error(f"No se pudo guardar: {e}")