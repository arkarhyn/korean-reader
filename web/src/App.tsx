import { useEffect } from "react";
import { Route, Routes } from "react-router";
import { syncer } from "./sync";
import Library from "./views/Library";
import Placement from "./views/Placement";
import Reader from "./views/Reader";
import { WordSetChecklist, WordSetList } from "./views/WordSets";

export default function App() {
  useEffect(() => syncer.start(), []);
  return (
    <Routes>
      <Route path="/" element={<Library />} />
      <Route path="/read/:id" element={<Reader />} />
      <Route path="/placement" element={<Placement />} />
      <Route path="/words" element={<WordSetList />} />
      <Route path="/words/:setId" element={<WordSetChecklist />} />
    </Routes>
  );
}
