import { createClient } from '@/utils/supabase';

export default async function Ledgers() {
  const supabase = await createClient();
  const { data: ledgers } = await supabase
    .from("ledgers")
    .select()
    .limit(10);

  return <pre>{JSON.stringify(ledgers, null, 2)}</pre>
}
