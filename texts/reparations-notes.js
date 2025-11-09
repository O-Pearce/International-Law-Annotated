// v6 notes header: attach to window, avoid const-scoped globals
window.NOTES = window.NOTES || {};
function addNote(para, author, text, title="", source="") {
  if (!window.NOTES[para]) window.NOTES[para] = [];
  window.NOTES[para].push({ author, title, text, source });
}
addNote("para-XX", "Jane Doe", "Test", "", "");


console.log('✅ notes loaded', Object.keys(window.NOTES));

;(function(){ window.NOTES_READY = true; window.dispatchEvent(new Event('notes:ready')); })();
