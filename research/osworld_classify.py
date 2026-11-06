import json, os, collections, re
base=r"D:\dev\interface-compiler\research\OSWorld\evaluation_examples"
test=json.load(open(os.path.join(base,"test_all.json")))
DOC={"vm_file","cache_file","googledrive_file","cloud_file","content_from_vm_file","audio_in_slide","background_image_in_slide","list_directory","python_test_suite_result","shortcuts_on_desktop"}
CFG={"vlc_config","gimp_config_file","vscode_config","bookmarks","history","cookie_data","default_search_engine","profile_name","chrome_font_size","data_delete_automacally","chrome_appearance_mode_ui","new_startup_page","enable_do_not_track","enable_safe_browsing","vm_wallpaper","default_video_player","find_unpacked_extension_path","find_installed_extension_name"}
LIVE={"active_url_from_accessTree","active_tab_html_parse","active_tab_url_parse","active_tab_url_and_body_text","active_tab_info","accessibility_tree","open_tabs_info","page_info","url_path_parse","url_dashPart","vlc_playing_info","vm_screen_size"}
CMD={"vm_command_line","vm_terminal_output","vm_command_error"}
cat=collections.Counter(); bydom=collections.defaultdict(collections.Counter)
cmds=[]; saved_by_evaluator=0; doc_tasks=0
for dom,ids in test.items():
  for i in ids:
    t=json.load(open(os.path.join(base,"examples",dom,i+".json"),encoding="utf-8"))
    ev=t.get("evaluator",{})
    f=ev.get("func"); f=f if isinstance(f,list) else [f]
    if "infeasible" in f: c="infeasible"
    else:
      r=ev.get("result"); rs=r if isinstance(r,list) else ([r] if r else [])
      ts={x.get("type") for x in rs}
      if not ts: c="none"
      elif ts<=DOC: c="file_document"
      elif ts<=DOC|CFG: c="file_settings"
      elif ts&LIVE: c="live_app_state"
      elif ts&CMD:
        c="command"
        for x in rs:
          if x.get("type") in CMD: cmds.append((dom,i[:8],str(x.get("command"))[:160],t["instruction"][:80]))
      else: c="other:"+",".join(sorted(ts))
      if c=="file_document":
        doc_tasks+=1
        pc=json.dumps(ev.get("postconfig",[]))
        if re.search(r"ctrl.{0,20}s['\"]|hotkey\(.{0,10}ctrl.{0,10}s|\"s\"\]", pc) or "pyautogui.hotkey" in pc and "'s'" in pc: saved_by_evaluator+=1
    cat[c]+=1; bydom[dom][c]+=1
print("TOTAL",sum(cat.values())); print(cat.most_common())
for d,c in bydom.items(): print(d,dict(c))
print("file_document tasks where evaluator postconfig saves (ctrl+s):",saved_by_evaluator,"of",doc_tasks)
print("COMMAND TASKS",len(cmds))
for c in cmds: print(" ",c)
