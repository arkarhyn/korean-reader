import { useEffect } from "react";
import { Route, Routes } from "react-router";
import { syncer } from "./sync";
import Library from "./views/Library";
import Reader from "./views/Reader";

export default function App() {
  useEffect(() => syncer.start(), []);
  return (
    <Routes>
      <Route path="/" element={<Library />} />
      <Route path="/read/:id" element={<Reader />} />
    </Routes>
  );
}
