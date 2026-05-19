import UsersAdminPanel from '@/components/createUserForm'; // Убедитесь, что путь верный

export default function UsersPage() {
  return (
    <div className="container mx-auto px-4 py-8">
      <UsersAdminPanel />
    </div>
  );
}