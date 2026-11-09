-- supabase_tablas.sql - Pega TODO este texto en Supabase -> SQL Editor -> New query -> Run.
-- Crea las tablas de la app. Con RLS activado y sin reglas, NADIE puede leerlas desde afuera:
-- solo la app (con la clave secreta "service_role", que vive en los secrets) puede.

create table if not exists usuarios (
  email text primary key,
  nombre text not null,
  institucion text,
  genero text,
  edad int,
  rol text not null default 'estudiante',         -- superadmin, profesor, estudiante, inversionista
  aprobado boolean not null default true,         -- los profesores esperan tu aprobación
  acepta_terminos boolean not null,
  acepta_datos boolean not null,
  acepta_contacto boolean not null default false,
  creado timestamptz not null default now()
);

create table if not exists operaciones (           -- Mis activos (cartera 'real') y el simulador de cada usuario ('sim')
  id bigserial primary key,
  email text not null,
  cartera text not null,
  "Fecha" timestamp, "Activo" text, "Tipo" text, "Precio" double precision, "Cantidad" double precision,
  "Moneda" text, "Nota" text, "Tasa_COP" double precision, "Costo_COP" double precision, "Origen" text,
  "Precio_COP" double precision, "Precio_USD" double precision
);
create index if not exists operaciones_usuario on operaciones (email, cartera);

create table if not exists ajustes (               -- configuración del simulador, stops personales...
  email text not null,
  clave text not null,
  valor jsonb,
  primary key (email, clave)
);

create table if not exists diario_errores (
  id bigserial primary key,
  email text not null,
  "Fecha_venta" text, "Cartera" text, "Activo" text, "Resultado" double precision, "Razon" text, "Anotado" text
);

alter table usuarios enable row level security;
alter table operaciones enable row level security;
alter table ajustes enable row level security;
alter table diario_errores enable row level security;

-- Almacenamiento privado para los archivos compartidos (ranking, noticias, precios comprimidos...)
insert into storage.buckets (id, name, public) values ('datos', 'datos', false) on conflict (id) do nothing;
