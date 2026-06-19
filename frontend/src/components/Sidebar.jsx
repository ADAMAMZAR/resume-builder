import { NavLink } from "react-router-dom";

const navItems = [
  { to: "/applications/new", label: "New Application" },
  { to: "/applications", label: "Applications" },
  { to: "/skills", label: "My Skills" },
  { to: "/settings", label: "Settings" },
];

function linkClasses({ isActive }) {
  return [
    "block rounded-lg px-4 py-2 text-sm font-medium",
    isActive ? "bg-white text-black" : "text-gray-300 hover:bg-gray-800",
  ].join(" ");
}

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-60 flex-col bg-black px-4 py-6">
      <div className="mb-8 px-2 text-lg font-bold text-white">CareerDraft</div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} className={linkClasses}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
