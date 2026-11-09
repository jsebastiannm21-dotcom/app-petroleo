-- supabase_seguridad.sql - Pega TODO en Supabase -> SQL Editor -> New query -> Run.
-- 1) Activa la seguridad por fila (RLS) en TODAS las tablas de la app (si ya estaba, no cambia nada ni borra datos).
--    Con RLS y sin reglas, nadie de afuera puede leer ni escribir: solo la app con su clave secreta (service_role).
alter table usuarios enable row level security;
alter table operaciones enable row level security;
alter table ajustes enable row level security;
alter table diario_errores enable row level security;
-- 2) Muestra el resultado: todas deben decir "true" en rls_activado, y el almacenamiento "datos" debe decir public = false.
select c.relname as tabla, c.relrowsecurity as rls_activado,
       (select count(*) from pg_policies p where p.tablename = c.relname) as reglas_abiertas
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r'
union all
select 'almacenamiento: ' || id, not public, 0 from storage.buckets;
