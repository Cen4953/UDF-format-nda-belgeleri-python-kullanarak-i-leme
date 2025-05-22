from tkinter import filedialog, messagebox, Tk, StringVar
from tkinter import ttk
import zipfile
import os
import shutil
import xml.etree.ElementTree as ET
import datetime
import re

def create_form():
    root = Tk()
    root.title("UDF Düzenleme (Blok Bazlı Length) v13")
    root.geometry("800x350")  # Burayı istediğiniz gibi değiştirin
    root.configure(bg="#f5f6fa")

    style = ttk.Style()
    style.theme_use("clam")

    # Oval ve modern Entry için stil
    style.configure("RoundedEntry.TEntry",
                    relief="flat",
                    padding=8,
                    borderwidth=0,
                    foreground="#222",
                    fieldbackground="#fff",
                    background="#fff",
                    bordercolor="#d1d8e0",
                    focusthickness=2,
                    focuscolor="#4a90e2")

    # Modern Label için stil
    style.configure("Modern.TLabel",
                    background="#f5f6fa",
                    font=("Segoe UI", 11))

    # Oval ve mavi Button için stil
    style.configure("RoundedBlue.TButton",
                    foreground="#fff",
                    background="#2980ff",
                    borderwidth=0,
                    focusthickness=3,
                    focuscolor="#2980ff",
                    font=("Segoe UI", 11, "bold"),
                    padding=8)
    style.map("RoundedBlue.TButton",
              background=[("active", "#1565c0")])

    # Label ve Entry'ler (YAN YANA)
    form_frame = ttk.Frame(root, style="Modern.TLabel")
    form_frame.pack(pady=30, padx=30, fill="x")

    # Ad Soyad
    ttk.Label(form_frame, text="Ad Soyad (Tamamı):", style="Modern.TLabel").grid(row=0, column=0, sticky="e", padx=(0,10), pady=8)
    name_var = StringVar()
    name_entry = ttk.Entry(form_frame, textvariable=name_var, style="RoundedEntry.TEntry")
    name_entry.grid(row=0, column=1, sticky="we", pady=8)

    # TCKN
    ttk.Label(form_frame, text="TCKN:", style="Modern.TLabel").grid(row=1, column=0, sticky="e", padx=(0,10), pady=8)
    tckn_var = StringVar()
    tckn_entry = ttk.Entry(form_frame, textvariable=tckn_var, style="RoundedEntry.TEntry")
    tckn_entry.grid(row=1, column=1, sticky="we", pady=8)

    # Sütun genişliği ayarı
    form_frame.columnconfigure(1, weight=1)

    def process_udf():
        name_full = name_entry.get().strip()
        tckn = tckn_entry.get().strip()

        print(f"\n--- Yeni İşlem Başlıyor ({datetime.datetime.now()}) [Blok Bazlı Length v13] ---")
        if not name_full or not tckn: messagebox.showerror("Hata", "Tüm alanları doldurun!"); return
        udf_path = filedialog.askopenfilename(title="UDF Şablon Seçin", filetypes=[("UDF Dosyaları", "*.udf")])
        if not udf_path: return

        temp_dir = 'temp_udf_v13_debug'
        tc_placeholder_str = "{{TC}}"
        name_placeholder_str = "{{AdSy}}"
        
        # (placeholder, original_start, original_len, new_value, new_len, length_diff)
        modifications_applied_to_content = [] 
        xml_file_name_to_process = None

        try:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            print(f"DEBUG: Geçici klasör: {temp_dir}")

            with zipfile.ZipFile(udf_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                # ... (Ana XML dosyası bulma mantığı v12 ile aynı) ...
                main_xml_candidates = ['content.xml']
                found_xml_files_in_zip = [name for name in zip_ref.namelist() if name.lower().endswith('.xml')]
                for candidate in main_xml_candidates:
                    for found_file in found_xml_files_in_zip:
                        if candidate.lower() == found_file.lower():
                            xml_file_name_to_process = found_file; break
                    if xml_file_name_to_process: break
                if not xml_file_name_to_process and found_xml_files_in_zip:
                    xml_file_name_to_process = found_xml_files_in_zip[0]
                    print(f"UYARI: Ana XML ('content.xml') bulunamadı. '{xml_file_name_to_process}' işlenecek.")
                elif not found_xml_files_in_zip:
                    messagebox.showerror("Hata", "UDF'de XML dosyası bulunamadı."); shutil.rmtree(temp_dir); return
            
            xml_path = os.path.join(temp_dir, xml_file_name_to_process)
            if not os.path.exists(xml_path):
                 messagebox.showerror("Hata", f"XML dosyası ({xml_file_name_to_process}) bulunamadı."); shutil.rmtree(temp_dir); return
            
            print(f"DEBUG: İşlenecek XML: {xml_path}")

            tree = ET.parse(xml_path)
            root_xml = tree.getroot()
            
            content_element = root_xml.find('content') 
            elements_root = root_xml.find('elements')

            if content_element is None or not hasattr(content_element, 'text') or content_element.text is None:
                messagebox.showerror("Hata", "<content> elementi/metni bulunamadı."); shutil.rmtree(temp_dir); return

            original_main_content_text = content_element.text if content_element.text is not None else ""
            
            # 1. Ana <content> metninde yapılacak değişiklikleri ve bilgilerini topla
            # Bu bilgiler, hem ana metni güncellemek hem de <elements> bloklarını ayarlamak için kullanılacak.
            # original_start, original_len, new_value, new_len, length_diff
            placeholder_definitions = []
            for ph_text, new_value_str in [(tc_placeholder_str, tckn), (name_placeholder_str, name_full)]:
                for match in re.finditer(re.escape(ph_text), original_main_content_text):
                    placeholder_definitions.append({
                        "placeholder": ph_text,
                        "original_start": match.start(),
                        "original_len": len(ph_text),
                        "new_value": new_value_str,
                        "new_len": len(new_value_str),
                        "length_diff": len(new_value_str) - len(ph_text)
                    })
            
            # Değişiklikleri orijinal başlangıç pozisyonlarına göre sırala (offset hesaplaması için önemli)
            placeholder_definitions.sort(key=lambda x: x["original_start"])

            # 2. Ana <content> metnini güncelle (değişiklikleri sondan başa doğru uygulayarak)
            updated_main_content_text = original_main_content_text
            for mod_info in sorted(placeholder_definitions, key=lambda x: x["original_start"], reverse=True):
                start, orig_len, new_val = mod_info["original_start"], mod_info["original_len"], mod_info["new_value"]
                updated_main_content_text = updated_main_content_text[:start] + new_val + updated_main_content_text[start + orig_len:]
                print(f"DEBUG Content Update: '{mod_info['placeholder']}' Orijinal ({start},len {orig_len}) -> '{new_val}'")
            content_element.text = updated_main_content_text
            print(f"DEBUG: <content> metni güncellendi. Yeni uzunluk: {len(content_element.text)}")

            # 3. <elements> bölümündeki offset ve length değerlerini güncelle
            if elements_root is not None:
                print(f"DEBUG: <elements> bölümü işleniyor ({len(placeholder_definitions)} potansiyel değişiklik).")
                for el_content_tag in elements_root.findall('.//content[@startOffset][@length]'):
                    try:
                        original_tag_offset = int(el_content_tag.get('startOffset'))
                        original_tag_length = int(el_content_tag.get('length'))
                        original_tag_end_exclusive = original_tag_offset + original_tag_length

                        # A. Bu tag'in yeni startOffset'ını hesapla
                        new_tag_offset = original_tag_offset
                        for mod_def in placeholder_definitions: # placeholder_definitions original_start'a göre sıralı
                            mod_original_start = mod_def["original_start"]
                            mod_original_end_exclusive = mod_original_start + mod_def["original_len"]
                            
                            if mod_original_end_exclusive <= original_tag_offset: # Değişiklik tamamen bu tag'den önce bittiyse
                                new_tag_offset += mod_def["length_diff"]
                            # Eğer değişiklik bu tag içinde başlıyorsa, offset'i etkilemez, sadece length'i.
                            # Eğer değişiklik bu tag'den önce başlayıp içine taşıyorsa, bu daha karmaşık.
                            # Şimdilik, sadece tamamen önce bitenlerin offset'i etkilediğini varsayalım.
                            # Bu, "8" ve "d" sorununu çözebilir.

                        # B. Bu tag'in yeni length'ini hesapla
                        # Orijinal <content> metninden bu bloğa karşılık gelen dilimi al
                        original_slice_for_this_tag = original_main_content_text[original_tag_offset:original_tag_end_exclusive]
                        
                        # Bu dilim üzerinde, içine düşen yer tutucu değişikliklerini uygula
                        current_slice_text = original_slice_for_this_tag
                        slice_modifications = []

                        for mod_def in placeholder_definitions:
                            mod_original_start_global = mod_def["original_start"]
                            mod_original_end_global = mod_original_start_global + mod_def["original_len"]

                            # Modifikasyon bu dilimle kesişiyor mu?
                            # Dilim global aralığı: [original_tag_offset, original_tag_end_exclusive)
                            # Mod   global aralığı: [mod_original_start_global, mod_original_end_global)
                            
                            overlap_start_global = max(original_tag_offset, mod_original_start_global)
                            overlap_end_global = min(original_tag_end_exclusive, mod_original_end_global)

                            if overlap_start_global < overlap_end_global: # Kesişim var
                                # Modifikasyonun dilim içindeki göreli pozisyonları
                                relative_mod_start_in_slice = mod_original_start_global - original_tag_offset
                                # Eğer modifikasyon dilimden önce başlıyorsa, dilim içindeki başlangıcı 0 olur.
                                relative_mod_start_in_slice = max(0, relative_mod_start_in_slice)
                                
                                # Orijinal yer tutucunun dilim içindeki kısmı
                                original_placeholder_part_in_slice = mod_def["placeholder"][
                                    max(0, original_tag_offset - mod_original_start_global) : \
                                    min(mod_def["original_len"], original_tag_end_exclusive - mod_original_start_global)
                                ]
                                if not original_placeholder_part_in_slice: continue # Bu mod bu dilimi etkilemiyor

                                # Yeni değerin dilim içindeki kısmı (bu daha karmaşık, tüm yeni değeri mi almalı?)
                                # Şimdilik, eğer yer tutucunun bir kısmı bile dilimdeyse, tüm yeni değeri oraya koymaya çalışalım
                                # Bu, eğer yer tutucu dilimi aşıyorsa sorun yaratır.
                                # Daha doğru bir yol, yer tutucunun dilim içindeki kısmını, yeni değerin orantılı kısmıyla değiştirmek.
                                # Ama bu çok karmaşıklaşır.
                                # Basitleştirilmiş: Eğer yer tutucunun başlangıcı dilimdeyse, işlem yap.
                                if mod_original_start_global >= original_tag_offset and mod_original_start_global < original_tag_end_exclusive:
                                    slice_modifications.append({
                                        "placeholder": mod_def["placeholder"],
                                        "relative_start": relative_mod_start_in_slice,
                                        "original_len_in_slice": len(original_placeholder_part_in_slice), # Sadece dilimdeki uzunluk
                                        "new_value": mod_def["new_value"], # Tüm yeni değer
                                    })
                        
                        # Dilimdeki değişiklikleri sondan başa doğru uygula
                        slice_modifications.sort(key=lambda x: x["relative_start"], reverse=True)
                        for slice_mod in slice_modifications:
                            s_start = slice_mod["relative_start"]
                            s_orig_len = slice_mod["original_len_in_slice"]
                            s_new_val = slice_mod["new_value"] # Tüm yeni değeri kullanıyoruz, bu riskli olabilir.

                            # Eğer original_len_in_slice, placeholder'ın tam uzunluğu değilse
                            # (yani placeholder dilimi aşıyorsa), bu değiştirme hatalı olabilir.
                            # Sadece tam olarak dilim içinde kalan placeholder'ları değiştirmek daha güvenli olabilir.
                            # Ya da, yeni değerin sadece dilime sığan kısmını almak.

                            # Güvenli yaklaşım: Eğer placeholder tam olarak bu dilim tarafından temsil ediliyorsa değiştir.
                            is_full_placeholder_in_slice = False
                            for main_mod_def in placeholder_definitions:
                                if main_mod_def["original_start"] == original_tag_offset + s_start and \
                                   main_mod_def["original_len"] == s_orig_len:
                                   is_full_placeholder_in_slice = True
                                   break
                            
                            if is_full_placeholder_in_slice:
                                current_slice_text = current_slice_text[:s_start] + \
                                                     s_new_val + \
                                                     current_slice_text[s_start + s_orig_len:]
                            else:
                                print(f"  SKIPPING partial placeholder modification in slice for tag ({original_tag_offset},{original_tag_length}) for placeholder at {original_tag_offset + s_start}")


                        new_tag_length = len(current_slice_text)

                        # Son kontroller ve atama
                        if new_tag_offset != original_tag_offset:
                            el_content_tag.set('startOffset', str(new_tag_offset))
                        if new_tag_length != original_tag_length and new_tag_length >=0:
                            el_content_tag.set('length', str(new_tag_length))
                        elif new_tag_length < 0:
                            el_content_tag.set('length', '0')

                        if original_tag_offset != new_tag_offset or original_tag_length != new_tag_length:
                             print(f"  DEBUG Elements Updated v13: Original=({original_tag_offset},{original_tag_length}) -> New=({new_tag_offset},{new_tag_length})")
                    
                    except ValueError: print(f"  UYARI Elements: Geçersiz offset/length: {el_content_tag.attrib}")
                    except Exception as ex_el: print(f"  HATA Elements: İşlenirken: {ex_el} (Attrib: {el_content_tag.attrib})")
            else:
                print("DEBUG: <elements> bölümü bulunmadığı için ayarlama yapılmadı.")

            # ... (dosyaya yazma ve UDF paketleme v12 ile aynı) ...
            debug_modified_xml_filename = f"DEBUG_MODIFIED_UDF_v13_{os.path.basename(xml_file_name_to_process)}"
            tree.write(os.path.join(temp_dir, debug_modified_xml_filename), encoding='utf-8', xml_declaration=True, method="xml")
            print(f"BİLGİ: Değiştirilmiş XML debug için kaydedildi: {os.path.join(temp_dir, debug_modified_xml_filename)}")
            tree.write(xml_path, encoding='utf-8', xml_declaration=True, method="xml")
            
            new_udf_path = filedialog.asksaveasfilename(title="Düzenlenmiş UDF Kaydet", defaultextension=".udf", filetypes=[("UDF Dosyaları", "*.udf")], initialfile=f"Duzenlenmis_v13_{os.path.basename(udf_path)}")
            if not new_udf_path: shutil.rmtree(temp_dir); return

            with zipfile.ZipFile(new_udf_path, 'w', zipfile.ZIP_DEFLATED) as zip_output:
                # ... (zip paketleme v12 ile aynı) ...
                for foldername, _, filenames_in_dir in os.walk(temp_dir):
                    for filename_to_zip in filenames_in_dir:
                        if filename_to_zip == debug_modified_xml_filename: continue
                        file_path_to_zip = os.path.join(foldername, filename_to_zip)
                        if not os.path.isfile(file_path_to_zip): continue
                        arcname = os.path.relpath(file_path_to_zip, temp_dir)
                        zip_output.write(file_path_to_zip, arcname)
            
            print(f"DEBUG: Yeni UDF oluşturuldu: {new_udf_path}")
            # ... (messagebox bilgilendirme v12 ile aynı) ...
            tc_changed_count = sum(1 for m in placeholder_definitions if m["placeholder"] == tc_placeholder_str and m["new_value"] != m["placeholder"]) # Değişip değişmediğini kontrol et
            name_changed_count = sum(1 for m in placeholder_definitions if m["placeholder"] == name_placeholder_str and m["new_value"] != m["placeholder"])
            messagebox.showinfo("İşlem Sonucu", f"UDF (v13) güncellendi: '{os.path.basename(new_udf_path)}'.\nTC Değişimi: {tc_changed_count}\nAdSoyad Değişimi: {name_changed_count}\nLütfen sonucu dikkatlice kontrol edin.")

        except Exception as e:
            messagebox.showerror("Genel Hata", f"İşlem başarısız: {str(e)}")
            import traceback; traceback.print_exc() 
        finally:
            # if os.path.exists(temp_dir): shutil.rmtree(temp_dir) 
            print(f"--- İşlem Tamamlandı ({datetime.datetime.now()}) ---\n")

    ttk.Button(root, text="UDF Şablonu Seç ve Değiştir ", style="RoundedBlue.TButton", command=process_udf).pack(pady=25, ipadx=10, ipady=2)

    root.mainloop()

if __name__ == "__main__":
    create_form()