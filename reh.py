import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import webbrowser
from geopy.geocoders import Nominatim

class ContactManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Gelişmiş Rehber Programı")
        self.root.geometry("1000x650")
        
        # Veritabanı bağlantısı
        self.conn = sqlite3.connect('rehber.db')
        self.c = self.conn.cursor()
        self.create_table()
        
        # UI Teması
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('Treeview', rowheight=25)
        
        self.create_widgets()
        self.load_contacts()
        
    def create_table(self):
        self.c.execute('''CREATE TABLE IF NOT EXISTS contacts (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL,
                         phone TEXT,
                         email TEXT,
                         address TEXT,
                         category TEXT,
                         notes TEXT)''')
        self.conn.commit()
    
    def create_widgets(self):
        # Main Frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left Frame (Form)
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Right Frame (Contacts List)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Contact Form
        form_frame = ttk.LabelFrame(left_frame, text="Kişi Bilgileri")
        form_frame.pack(fill=tk.X, pady=5)
        
        labels = ["Ad-Soyad:", "Telefon:", "E-posta:", "Adres:", "Kategori:", "Notlar:"]
        self.entries = {}
        
        for i, text in enumerate(labels):
            ttk.Label(form_frame, text=text).grid(row=i, column=0, sticky=tk.W, padx=5, pady=5)
            if text == "Notlar:":
                entry = tk.Text(form_frame, width=30, height=4)
            else:
                entry = ttk.Entry(form_frame, width=30)
            entry.grid(row=i, column=1, padx=5, pady=5)
            self.entries[text.split(":")[0].lower()] = entry
        
        # Buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        buttons = [
            ("Ekle", self.add_contact),
            ("Güncelle", self.update_contact),
            ("Sil", self.delete_contact),
            ("Temizle", self.clear_form),
            ("Haritada Göster", self.show_on_map),
            ("CSV Al", self.export_csv),
            ("CSV Yükle", self.import_csv)
        ]
        
        for i, (text, command) in enumerate(buttons):
            btn = ttk.Button(btn_frame, text=text, command=command)
            btn.pack(fill=tk.X, padx=5, pady=2)
        
        # Search Frame
        search_frame = ttk.LabelFrame(right_frame, text="Arama ve Filtreleme")
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(search_frame, text="Ara:").pack(side=tk.LEFT, padx=5)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", self.search_contacts)
        
        ttk.Label(search_frame, text="Kategori:").pack(side=tk.LEFT, padx=5)
        self.category_var = tk.StringVar()
        self.category_dropdown = ttk.Combobox(search_frame, 
                                            textvariable=self.category_var)
        self.category_dropdown.pack(side=tk.LEFT, padx=5)
        self.category_dropdown.bind("<<ComboboxSelected>>", self.filter_by_category)
        
        # Contacts Treeview
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ("id", "name", "phone", "email", "category")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        for col in columns:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=100)
        
        self.tree.column("name", width=200)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def load_contacts(self):
        self.tree.delete(*self.tree.get_children())
        self.c.execute("SELECT * FROM contacts")
        contacts = self.c.fetchall()
        
        for contact in contacts:
            self.tree.insert("", tk.END, values=contact)
        
        self.update_category_dropdown()
    
    def update_category_dropdown(self):
        self.c.execute("SELECT DISTINCT category FROM contacts WHERE category IS NOT NULL AND category != ''")
        categories = [cat[0] for cat in self.c.fetchall()]
        categories.insert(0, "Tüm Kategoriler")
        self.category_dropdown["values"] = categories
        self.category_var.set("Tüm Kategoriler")
    
    def add_contact(self):
        data = {
            "name": self.entries["ad-soyad"].get(),
            "phone": self.entries["telefon"].get(),
            "email": self.entries["e-posta"].get(),
            "address": self.entries["adres"].get(),
            "category": self.entries["kategori"].get(),
            "notes": self.entries["notlar"].get("1.0", tk.END).strip()
        }
        
        if not data["name"]:
            messagebox.showwarning("Uyarı", "Ad-Soyad alanı boş olamaz!")
            return
        
        self.c.execute('''INSERT INTO contacts 
                        (name, phone, email, address, category, notes)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                    (data["name"], data["phone"], data["email"], 
                     data["address"], data["category"], data["notes"]))
        self.conn.commit()
        self.load_contacts()
        self.clear_form()
        messagebox.showinfo("Başarılı", "Kişi başarıyla eklendi!")
    
    def update_contact(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen güncellemek için bir kişi seçin!")
            return
        
        contact_id = self.tree.item(selected[0])["values"][0]
        data = {
            "name": self.entries["ad-soyad"].get(),
            "phone": self.entries["telefon"].get(),
            "email": self.entries["e-posta"].get(),
            "address": self.entries["adres"].get(),
            "category": self.entries["kategori"].get(),
            "notes": self.entries["notlar"].get("1.0", tk.END).strip()
        }
        
        if not data["name"]:
            messagebox.showwarning("Uyarı", "Ad-Soyad alanı boş olamaz!")
            return
        
        self.c.execute('''UPDATE contacts SET 
                        name=?, phone=?, email=?, address=?, category=?, notes=?
                        WHERE id=?''',
                    (data["name"], data["phone"], data["email"], 
                     data["address"], data["category"], data["notes"], contact_id))
        self.conn.commit()
        self.load_contacts()
        messagebox.showinfo("Başarılı", "Kişi başarıyla güncellendi!")
    
    def delete_contact(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir kişi seçin!")
            return
        
        if messagebox.askyesno("Onay", "Seçili kişiyi silmek istediğinize emin misiniz?"):
            contact_id = self.tree.item(selected[0])["values"][0]
            self.c.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
            self.conn.commit()
            self.load_contacts()
            self.clear_form()
    
    def clear_form(self):
        for entry in self.entries.values():
            if isinstance(entry, ttk.Entry):
                entry.delete(0, tk.END)
            elif isinstance(entry, tk.Text):
                entry.delete("1.0", tk.END)
    
    def on_tree_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
        
        contact_id = self.tree.item(selected[0])["values"][0]
        self.c.execute("SELECT * FROM contacts WHERE id=?", (contact_id,))
        contact = self.c.fetchone()
        
        self.entries["ad-soyad"].delete(0, tk.END)
        self.entries["ad-soyad"].insert(0, contact[1])
        
        self.entries["telefon"].delete(0, tk.END)
        if contact[2]:
            self.entries["telefon"].insert(0, contact[2])
        
        self.entries["e-posta"].delete(0, tk.END)
        if contact[3]:
            self.entries["e-posta"].insert(0, contact[3])
        
        self.entries["adres"].delete(0, tk.END)
        if contact[4]:
            self.entries["adres"].insert(0, contact[4])
        
        self.entries["kategori"].delete(0, tk.END)
        if contact[5]:
            self.entries["kategori"].insert(0, contact[5])
        
        self.entries["notlar"].delete("1.0", tk.END)
        if contact[6]:
            self.entries["notlar"].insert("1.0", contact[6])
    
    def search_contacts(self, event=None):
        query = self.search_entry.get().lower()
        
        for item in self.tree.get_children():
            values = [str(v).lower() for v in self.tree.item(item)["values"]]
            if any(query in value for value in values):
                self.tree.selection_add(item)
                self.tree.see(item)
            else:
                self.tree.selection_remove(item)
    
    def filter_by_category(self, event=None):
        category = self.category_var.get()
        if category == "Tüm Kategoriler":
            for item in self.tree.get_children():
                self.tree.selection_remove(item)
            return
        
        for item in self.tree.get_children():
            contact_category = self.tree.item(item)["values"][4]
            if contact_category == category:
                self.tree.selection_add(item)
                self.tree.see(item)
            else:
                self.tree.selection_remove(item)
    
    def show_on_map(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen haritada görmek için bir kişi seçin!")
            return
        
        address = self.entries["adres"].get()
        if not address:
            messagebox.showwarning("Uyarı", "Seçilen kişinin adresi yok!")
            return
        
        try:
            geolocator = Nominatim(user_agent="rehber_app")
            location = geolocator.geocode(address)
            if location:
                url = f"https://www.openstreetmap.org/?mlat={location.latitude}&mlon={location.longitude}#map=16/{location.latitude}/{location.longitude}"
                webbrowser.open(url)
            else:
                messagebox.showerror("Hata", "Adres bulunamadı!")
        except Exception as e:
            messagebox.showerror("Hata", f"Harita gösterilirken hata oluştu: {str(e)}")
    
    def export_csv(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Dosyaları", "*.csv"), ("Tüm Dosyalar", "*.*")],
            title="CSV Olarak Kaydet"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["ID", "Ad-Soyad", "Telefon", "E-posta", "Adres", "Kategori", "Notlar"])
                
                self.c.execute("SELECT * FROM contacts")
                contacts = self.c.fetchall()
                writer.writerows(contacts)
            
            messagebox.showinfo("Başarılı", f"Rehber başarıyla {file_path} dosyasına kaydedildi!")
        except Exception as e:
            messagebox.showerror("Hata", f"CSV kaydedilirken hata oluştu: {str(e)}")
    
    def import_csv(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV Dosyaları", "*.csv"), ("Tüm Dosyalar", "*.*")],
            title="CSV Dosyasını Seç"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Başlık satırını atla
                
                for row in reader:
                    self.c.execute('''INSERT INTO contacts 
                                    (name, phone, email, address, category, notes)
                                    VALUES (?, ?, ?, ?, ?, ?)''',
                                (row[1], row[2], row[3], row[4], row[5], row[6]))
            
            self.conn.commit()
            self.load_contacts()
            messagebox.showinfo("Başarılı", "CSV dosyası başarıyla içe aktarıldı!")
        except Exception as e:
            messagebox.showerror("Hata", f"CSV okunurken hata oluştu: {str(e)}")
    
    def __del__(self):
        self.conn.close()

if __name__ == "__main__":
    root = tk.Tk()
    app = ContactManager(root)
    root.mainloop()
